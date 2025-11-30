from __future__ import annotations

import difflib
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None

import networkx as nx
import spacy
from llama_index.core import PromptTemplate, Settings
from llama_index.core.program import LLMTextCompletionProgram
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EntityVerificationResult(BaseModel):
    index: int
    is_same_entity: bool


class EntityVerificationBatch(BaseModel):
    results: List[EntityVerificationResult]


class EntityDeduplicator:
    def __init__(
        self,
        graph_store: Neo4jPropertyGraphStore,
        similarity_threshold: float = 0.9,
        word_edit_distance: int = 5,
        enable_apoc: bool = True,
        llm: Any = None,
    ):
        self.graph_store = graph_store
        self.similarity_threshold = similarity_threshold
        self.word_edit_distance = word_edit_distance
        self.enable_apoc = enable_apoc
        self.llm = llm
        self.embed_model = Settings.embed_model

        logger.info(f"EntityDeduplicator initialized: similarity_threshold={similarity_threshold}, word_edit_distance={word_edit_distance}")

    def _get_driver(self):
        driver = getattr(self.graph_store, "driver", None) or getattr(self.graph_store, "_driver", None)
        if driver is None:
            raise RuntimeError("Neo4j driver not available from property graph store")
        return driver

    def create_vector_index(self, embedding_dimension: int = 1536, name: str = "entity"):
        try:
            safe_name = "".join(c for c in name if c.isalnum() or c in "_")

            query = f"""
            CREATE VECTOR INDEX {safe_name} IF NOT EXISTS
            FOR (m:`__Entity__`)
            ON m.embedding
            OPTIONS {{indexConfig: {{
                `vector.dimensions`: $dimensions,
                `vector.similarity_function`: 'cosine'
            }}}}
            """

            self.graph_store.structured_query(query, param_map={"dimensions": embedding_dimension})

            logger.info(f"Created vector index '{safe_name}' on __Entity__ with {embedding_dimension} dimensions")

        except Exception as e:
            logger.error(f"Could not create vector index: {e}")
            raise e

    def find_duplicate_entities(self, use_llm: bool = True) -> List[Dict[str, Any]]:
        """
        Returns a list of dictionaries, each containing:
        - 'group': List[str] of entity names
        - 'source': str (e.g., 'apoc', 'exact', 'abbreviation', 'llm', 'consolidated')
        """
        try:
            all_groups_with_source = []

            if self.enable_apoc:
                apoc_groups = self._find_duplicates_with_apoc()
                for g in apoc_groups:
                    all_groups_with_source.append({"group": g, "source": "apoc_fuzzy"})
            else:
                non_apoc_groups = self._find_duplicates_without_apoc()
                for g in non_apoc_groups:
                    all_groups_with_source.append({"group": g, "source": "simple_fuzzy"})

            abbrev_groups = self._find_abbreviation_duplicates()
            for g in abbrev_groups:
                all_groups_with_source.append({"group": g, "source": "abbreviation_rule"})

            exact_groups = self._find_exact_duplicates()
            for g in exact_groups:
                all_groups_with_source.append({"group": g, "source": "exact_match"})

            if self.llm and use_llm:
                current_groups = [item["group"] for item in all_groups_with_source]
                candidate_pairs = self._find_candidates_for_llm(existing_groups=current_groups)

                if candidate_pairs:
                    llm_groups_with_source = self._verify_with_llm(candidate_pairs)
                    all_groups_with_source.extend(llm_groups_with_source)

            consolidated_groups = self._consolidate_groups_with_source(all_groups_with_source)

            return consolidated_groups
        except Exception as e:
            logger.error(f"Error in deduplication: {e}")
            raise e

    def _consolidate_groups_with_source(self, groups_with_source: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not groups_with_source:
            return []

        G = nx.Graph()
        node_sources = {}

        for item in groups_with_source:
            group = item["group"]
            source = item["source"]

            if not group:
                continue

            first_node = group[0]
            G.add_node(first_node)
            if first_node not in node_sources:
                node_sources[first_node] = set()
            node_sources[first_node].add(source)

            for i in range(1, len(group)):
                node = group[i]
                G.add_node(node)
                G.add_edge(first_node, node)

                if node not in node_sources:
                    node_sources[node] = set()
                node_sources[node].add(source)

        consolidated = []

        for component in nx.connected_components(G):
            if len(component) > 1:
                sources_in_component = set()
                for node in component:
                    sources_in_component.update(node_sources.get(node, set()))

                if len(sources_in_component) == 1:
                    final_source = list(sources_in_component)[0]
                else:
                    final_source = f"consolidated({', '.join(sorted(sources_in_component))})"

                consolidated.append({"group": sorted(list(component)), "source": final_source})

        return consolidated

    def _find_exact_duplicates(self) -> List[List[str]]:
        query = """
        MATCH (n:__Entity__)
        WITH toLower(n.name) as lower_name, collect(n) as nodes
        WHERE size(nodes) > 1
        RETURN [node in nodes | node.name] as names
        """
        try:
            result = self.graph_store.structured_query(query)
            groups = [row["names"] for row in result]
            if groups:
                logger.info(f"Found {len(groups)} exact duplicate groups")
            return groups
        except Exception as e:
            logger.error(f"Error finding exact duplicates: {e}")
            raise e

    def _find_abbreviation_duplicates(self) -> List[List[str]]:
        try:
            query = "MATCH (n:__Entity__) RETURN distinct n.name as name"
            result = self.graph_store.structured_query(query)
            all_names = [r["name"] for r in result if r["name"]]

            all_words = set()
            for name in all_names:
                words = re.split(r"[^a-zA-Z0-9]+", name)
                all_words.update(words)

            abbrev_tokens = {w for w in all_words if 2 <= len(w) <= 6 and w.isupper() and w.isalpha()}

            token_map = {}

            for name in all_names:
                for token in abbrev_tokens:
                    if f"({token})" in name:
                        pre_part = name.split(f"({token})")[0].strip()
                        if pre_part:
                            if self._is_abbreviation_of(token, pre_part):
                                if token not in token_map:
                                    token_map[token] = set()
                                token_map[token].add(pre_part)

                words = name.split()
                if len(words) < 2:
                    continue

                for token in abbrev_tokens:
                    if len(words) < len(token):
                        continue

                    for i in range(len(words) - len(token) + 1):
                        window = words[i : i + len(token)]
                        initials = "".join(w[0].upper() for w in window if w[0].isalpha())
                        if initials == token:
                            phrase = " ".join(window)
                            if phrase.upper() == token:
                                continue
                            if token not in token_map:
                                token_map[token] = set()
                            token_map[token].add(phrase)

            groups = []
            processed = set()

            for token, phrases in token_map.items():
                for phrase in phrases:
                    # Use regex for robust token matching (handles punctuation like "NEFAC,")
                    token_pattern = re.compile(rf"\b{re.escape(token)}\b")
                    names_with_token = [n for n in all_names if token_pattern.search(n)]
                    names_with_phrase = [n for n in all_names if phrase in n]

                    for n_phrase in names_with_phrase:
                        n_token_hypothetical = n_phrase.replace(phrase, token)

                        for n_token in names_with_token:
                            if n_token == n_token_hypothetical:
                                pair = sorted([n_phrase, n_token])
                                if tuple(pair) not in processed:
                                    groups.append(pair)
                                    processed.add(tuple(pair))

                            elif self._is_close_match(n_token, n_token_hypothetical):
                                pair = sorted([n_phrase, n_token])
                                if tuple(pair) not in processed:
                                    groups.append(pair)
                                    processed.add(tuple(pair))

            return groups
        except Exception as e:
            logger.error(f"Error finding abbreviation duplicates: {e}")
            raise e

    def _is_close_match(self, s1: str, s2: str) -> bool:
        def clean(s):
            return "".join(c.lower() for c in s if c.isalnum() or c.isspace())

        c1 = clean(s1)
        c2 = clean(s2)

        if c1 == c2:
            return True

        stop_words = {"of", "the", "and", "in", "for", "to", "a", "an", "at", "by", "from", "with"}

        tokens1 = set(w for w in c1.split() if w not in stop_words)
        tokens2 = set(w for w in c2.split() if w not in stop_words)

        if not tokens1 or not tokens2:
            return False

        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)

        jaccard = len(intersection) / len(union)

        if jaccard > 0.8:
            return True

        if abs(len(c1) - len(c2)) < 5:
            ratio = difflib.SequenceMatcher(None, c1, c2).ratio()
            return ratio > 0.9

        return False

    def _is_abbreviation_of(self, abbrev: str, full: str) -> bool:
        words = [w for w in full.split() if w[0].isalnum()]

        if len(words) < len(abbrev):
            return False

        initials = "".join(w[0].upper() for w in words)

        if initials == abbrev:
            return True

        stop_words = {"of", "the", "and", "in", "for", "to", "a", "an"}
        filtered_words = [w for w in words if w.lower() not in stop_words]
        filtered_initials = "".join(w[0].upper() for w in filtered_words)

        if filtered_initials == abbrev:
            return True

        return False

    def _find_duplicates_with_apoc(self) -> List[List[str]]:
        query = """
        MATCH (e:__Entity__)
        CALL {
            WITH e
            CALL db.index.vector.queryNodes('entity', 10, e.embedding)
            YIELD node, score
            WITH node, score
            WHERE score > toFloat($cutoff)
                AND size(node.name) > 5
                AND size(e.name) > 5
                AND labels(e) = labels(node)
                AND (
                    apoc.text.sorensenDiceSimilarity(toLower(node.name), toLower(e.name)) > 0.85
                    OR
                    apoc.text.levenshteinSimilarity(toLower(node.name), toLower(e.name)) > 0.90
                    OR
                    apoc.text.doubleMetaphone(node.name) = apoc.text.doubleMetaphone(e.name)
                )
            WITH node, score
            ORDER BY node.name
            RETURN collect(node) AS nodes
        }
        WITH distinct nodes
        WHERE size(nodes) > 1
        WITH collect([n in nodes | n.name]) AS results
        UNWIND range(0, size(results)-1, 1) as index
        WITH results, index, results[index] as result
        WITH apoc.coll.sort(reduce(acc = result, index2 IN range(0, size(results)-1, 1) |
                CASE WHEN index <> index2 AND
                    size(apoc.coll.intersection(acc, results[index2])) > 0
                    THEN apoc.coll.union(acc, results[index2])
                    ELSE acc
                END
        )) as combinedResult
        WITH distinct(combinedResult) as combinedResult
        WITH collect(combinedResult) as allCombinedResults
        UNWIND range(0, size(allCombinedResults)-1, 1) as combinedResultIndex
        WITH allCombinedResults[combinedResultIndex] as combinedResult,
             combinedResultIndex, allCombinedResults
        WHERE NOT any(x IN range(0,size(allCombinedResults)-1,1) 
            WHERE x <> combinedResultIndex
            AND apoc.coll.containsAll(allCombinedResults[x], combinedResult)
        )
        RETURN combinedResult
        """

        try:
            data = self.graph_store.structured_query(query, param_map={"cutoff": self.similarity_threshold, "distance": self.word_edit_distance})

            duplicate_groups = [row["combinedResult"] for row in data]

            logger.info(f"Found {len(duplicate_groups)} duplicate entity groups using APOC")
            for group in duplicate_groups:
                logger.debug(f"Duplicate group: {group}")

            return duplicate_groups

        except Exception as e:
            logger.error(f"Error in APOC-based deduplication: {e}")
            raise e

    def _find_duplicates_without_apoc(self) -> List[List[str]]:
        query = """
        MATCH (e:__Entity__)
        CALL {
            WITH e
            CALL db.index.vector.queryNodes('entity', 10, e.embedding)
            YIELD node, score
            WITH node, score
            WHERE score > toFloat($cutoff)
                AND labels(e) = labels(node)
                AND (toLower(node.name) CONTAINS toLower(e.name) 
                     OR toLower(e.name) CONTAINS toLower(node.name))
            WITH node, score
            ORDER BY node.name
            RETURN collect(node.name) AS names
        }
        WITH distinct names
        WHERE size(names) > 1
        RETURN names as combinedResult
        """

        try:
            data = self.graph_store.structured_query(query, param_map={"cutoff": self.similarity_threshold})

            duplicate_groups = [row["combinedResult"] for row in data]

            filtered_groups = self._remove_subset_groups(duplicate_groups)

            logger.info(f"Found {len(filtered_groups)} duplicate entity groups (no APOC)")
            return filtered_groups

        except Exception as e:
            logger.error(f"Error in non-APOC deduplication: {e}")
            raise e

    def _remove_subset_groups(self, groups: List[List[str]]) -> List[List[str]]:
        filtered = []
        for i, group in enumerate(groups):
            is_subset = False
            for j, other_group in enumerate(groups):
                if i != j and set(group).issubset(set(other_group)):
                    is_subset = True
                    break
            if not is_subset:
                filtered.append(group)
        return filtered

    def merge_duplicate_entities(
        self,
        duplicate_groups: Optional[List[Dict[str, Any]]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        if duplicate_groups is None:
            duplicate_groups = self.find_duplicate_entities()

        if not duplicate_groups:
            logger.info("No duplicate entities found to merge")
            return {"merged_groups": 0, "total_entities_merged": 0}

        merged_count = 0
        total_entities = 0

        for item in duplicate_groups:
            group = item["group"]
            source = item.get("source", "unknown")

            if len(group) < 2:
                continue

            canonical_name = sorted(group, key=lambda x: (-len(x), x))[0]
            duplicates = [name for name in group if name != canonical_name]

            logger.info(f"[Source: {source}] Merging {duplicates} into '{canonical_name}'")

            if not dry_run:
                self._merge_entity_group(canonical_name, duplicates)

            merged_count += 1
            total_entities += len(duplicates)

        stats = {
            "merged_groups": merged_count,
            "total_entities_merged": total_entities,
            "dry_run": dry_run,
        }

        logger.info(f"Entity deduplication complete: {stats}")
        return stats

    def _merge_entity_group(self, canonical_name: str, duplicates: List[str]):
        query = """
        MATCH (canonical:__Entity__ {name: $canonical_name})
        MATCH (duplicate:__Entity__)
        WHERE duplicate.name IN $duplicates

        WITH canonical, collect(duplicate) as duplicates
        WITH [canonical] + duplicates as nodesToMerge

        CALL apoc.refactor.mergeNodes(nodesToMerge, {
            properties: {
                name: 'discard',
                id: 'discard',
                embedding: 'discard',
                `.*`: 'overwrite'
            },
            mergeRels: true
        }) YIELD node

        RETURN node.name as merged_into, size(nodesToMerge) - 1 as merged_count
        """

        try:
            result = self.graph_store.structured_query(query, param_map={"canonical_name": canonical_name, "duplicates": duplicates})

            if result:
                count = result[0].get("merged_count", 0)
                logger.debug(f"Merged {count} entities into '{canonical_name}' using APOC")

        except Exception as e:
            logger.error(f"Error merging entity group: {e}")
            raise e

    def validate_duplicates(
        self,
        duplicate_groups: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        try:
            if duplicate_groups is None:
                duplicate_groups = self.find_duplicate_entities()

            def has_conflicting_years(names):
                years = set()
                for n in names:
                    matches = re.findall(r"\b(?:19|20)\d{2}\b", str(n))
                    years.update(matches)
                return len(years) > 1

            def has_conflicting_numbers_group(names):
                all_nums = []
                for n in names:
                    nums = set(re.findall(r"\d+(?:\.\d+)?", str(n)))
                    if nums:
                        all_nums.append(nums)

                if len(all_nums) < 2:
                    return False

                for i in range(len(all_nums)):
                    for j in range(i + 1, len(all_nums)):
                        if all_nums[i].isdisjoint(all_nums[j]):
                            return True
                return False

            def is_policy_vs_location(names):
                keywords = {"policy", "act", "law", "regulation", "protocol", "procedure", "guideline"}
                has_keyword = [any(k in str(n).lower() for k in keywords) for n in names]

                if all(has_keyword) or not any(has_keyword):
                    return False

                nlp = self._ensure_spacy_model()
                if nlp:
                    try:
                        has_gpe = False
                        has_law_or_work = False

                        for n in names:
                            doc = nlp(str(n))
                            for ent in doc.ents:
                                if ent.label_ == "GPE":
                                    has_gpe = True
                                elif ent.label_ in ["LAW", "WORK_OF_ART", "ORG"]:
                                    has_law_or_work = True

                        if has_gpe and has_law_or_work:
                            return True
                    except Exception:
                        pass

                location_indicators = {", rhode island", ", ri", "state of", "city of", "town of"}
                for i, n in enumerate(names):
                    if not has_keyword[i]:
                        if any(loc in str(n).lower() for loc in location_indicators):
                            return True
                        if str(n).strip().lower() == "rhode island":
                            return True
                return False

            false_positive_patterns = [
                (has_conflicting_years, "Contains different years"),
                (has_conflicting_numbers_group, "Contains conflicting numbers"),
                (is_policy_vs_location, "Merges Policy/Doc with Location"),
                (lambda names: any("draft" in str(n).lower() for n in names) and any("draft" not in str(n).lower() for n in names), "Mix of draft and non-draft"),
                (lambda names: any("Amended" in str(n) for n in names) and len(set(str(n).replace("Amended", "").strip() for n in names)) > 1, "Different base documents with amendments"),
            ]

            validated = []
            false_positives = []

            for item in duplicate_groups:
                group = item["group"]
                is_false_positive = False
                reason = None

                for pattern_fn, pattern_reason in false_positive_patterns:
                    if pattern_fn(group):
                        is_false_positive = True
                        reason = pattern_reason
                        break

                if is_false_positive:
                    logger.debug(f"False positive detected: {group} - {reason}")
                    false_positives.append(item)
                else:
                    validated.append(item)

            logger.info(f"Validation complete: {len(validated)} valid groups, " f"{len(false_positives)} false positives")

            return validated, false_positives
        except Exception as e:
            logger.error(f"Error validating duplicates: {e}")
            raise e

    def get_duplicate_stats(
        self,
        duplicate_groups: Optional[List[Dict[str, Any]]] = None,
        validated_groups: Optional[List[Dict[str, Any]]] = None,
        false_positives: Optional[List[Dict[str, Any]]] = None,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        try:
            count_query = "MATCH (e:__Entity__) RETURN count(e) as total"
            result = self.graph_store.structured_query(count_query)
            total_entities = result[0]["total"] if result else 0

            if duplicate_groups is None:
                duplicate_groups = self.find_duplicate_entities(use_llm=use_llm)

            if validated_groups is None:
                validated_groups, false_positives = self.validate_duplicates(duplicate_groups)

            if false_positives is None:
                false_positives = []

            total_duplicates = sum(len(item["group"]) - 1 for item in validated_groups)

            stats = {
                "total_entities": total_entities,
                "duplicate_groups_found": len(duplicate_groups),
                "validated_groups": len(validated_groups),
                "false_positive_groups": len(false_positives),
                "total_duplicate_entities": total_duplicates,
                "deduplication_potential": f"{(total_duplicates / max(total_entities, 1) * 100):.1f}%",
            }

            return stats

        except Exception as e:
            logger.error(f"Error getting duplicate stats: {e}")
            raise e

    def _find_candidates_for_llm(self, existing_groups: List[List[str]]) -> List[List[str]]:
        query = """
        MATCH (e:__Entity__)
        CALL {
            WITH e
            CALL db.index.vector.queryNodes('entity', 10, e.embedding)
            YIELD node, score
            WITH node, score
            WHERE score > 0.92
                AND e.id < node.id
                AND apoc.text.sorensenDiceSimilarity(toLower(node.name), toLower(e.name)) < 0.8
            RETURN node
        }
        RETURN e.name as name1, node.name as name2
        """
        try:
            result = self.graph_store.structured_query(query)
            candidates = []

            existing_pairs = set()
            for group in existing_groups:
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        pair = tuple(sorted([group[i], group[j]]))
                        existing_pairs.add(pair)

            for row in result:
                pair = sorted([row["name1"], row["name2"]])
                if tuple(pair) not in existing_pairs:
                    candidates.append(pair)

            if candidates:
                logger.info(f"Found {len(candidates)} candidate pairs for LLM verification")

            return candidates
        except Exception as e:
            logger.error(f"Error finding candidates for LLM: {e}")
            raise e

    def _has_conflicting_numbers(self, s1: str, s2: str) -> bool:
        """
        Checks if two strings contain conflicting numbers (e.g. "Section 3" vs "Section 2.5").
        Returns True if both strings have numbers but they don't overlap.
        """

        def extract_nums(s):
            return set(re.findall(r"\d+(?:\.\d+)?", s))

        nums1 = extract_nums(s1)
        nums2 = extract_nums(s2)

        if not nums1 or not nums2:
            return False

        return nums1.isdisjoint(nums2)

    def _is_token_sort_match(self, s1: str, s2: str, threshold: float = 88.0) -> bool:
        """
        Fuzzy match that handles token reordering (e.g. "ACLU RI" == "RI ACLU") and typos.
        Uses rapidfuzz for high performance and accuracy.
        """
        if self._has_conflicting_numbers(s1, s2):
            return False

        if fuzz:
            return fuzz.token_sort_ratio(s1, s2) > threshold

        logger.warning("rapidfuzz not found, falling back to slower difflib implementation")
        return self._is_token_sort_match_fallback(s1, s2, threshold / 100.0)

    def _is_token_sort_match_fallback(self, s1: str, s2: str, threshold: float) -> bool:
        def process(s):
            return "".join(c.lower() for c in s if c.isalnum() or c.isspace())

        c1 = process(s1)
        c2 = process(s2)

        t1 = sorted(c1.split())
        t2 = sorted(c2.split())

        s1_sorted = " ".join(t1)
        s2_sorted = " ".join(t2)

        return difflib.SequenceMatcher(None, s1_sorted, s2_sorted).ratio() > threshold

    def _verify_with_llm(self, candidates: List[List[str]]) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        verified_groups = []
        llm_candidates = []

        for pair in candidates:
            if self._is_token_sort_match(pair[0], pair[1]):
                logger.debug(f"Fast-verified pair (token sort): {pair}")
                verified_groups.append({"group": pair, "source": "rapidfuzz_token_sort"})
            else:
                llm_candidates.append(pair)

        if not llm_candidates:
            return verified_groups

        logger.info(f"Sending {len(llm_candidates)} pairs (out of {len(candidates)}) to LLM for verification")

        batch_size = 20

        for i in range(0, len(llm_candidates), batch_size):
            batch = llm_candidates[i : i + batch_size]

            pairs_text = ""
            for idx, pair in enumerate(batch):
                pairs_text += f"{idx}. {pair[0]} <-> {pair[1]}\n"

            prompt_tmpl = PromptTemplate(
                "You are a strict entity deduplication assistant.\n"
                "Analyze the following pairs of entity names and determine if they refer to the EXACT SAME real-world entity.\n"
                "\n"
                "Rules:\n"
                "1. Return TRUE only if they are synonyms, abbreviations, or minor spelling variations.\n"
                "2. Return FALSE if they are distinct entities, even if related (e.g., 'Report 2024' vs 'Report 2025').\n"
                "3. Return FALSE if one is a container and the other is content (e.g., 'Website' vs 'Article on Website').\n"
                "4. Return FALSE if they are different categories (e.g. Location vs Organization, Person vs Organization), even if one name is a subset of the other (e.g. 'Rhode Island' vs 'ACLU of Rhode Island').\n"
                "5. Return FALSE if numbers conflict (e.g. 'Section 3' vs 'Section 2.5').\n"
                "6. Return FALSE if one is a Document/Policy and the other is a Location/Government (e.g. 'RI BWC Policy' vs 'Rhode Island').\n"
                "7. Return FALSE if you are unsure.\n"
                "\n"
                "Pairs to analyze:\n"
                "{pairs_text}"
            )

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    prediction = self._predict_structured(prompt_tmpl=prompt_tmpl, pairs_text=pairs_text)
                    results = prediction.results

                    for res in results:
                        if res.is_same_entity and res.index < len(batch):
                            verified_groups.append({"group": batch[res.index], "source": "llm_verified"})

                    # Success - break retry loop
                    break

                except Exception as e:
                    is_rate_limit = "429" in str(e) or "ResourceExhausted" in str(e) or "rate limit" in str(e).lower()
                    if is_rate_limit and attempt < max_retries - 1:
                        sleep_time = 10 * (attempt + 1)
                        logger.warning(f"Rate limit hit during deduplication. Retrying in {sleep_time}s (Attempt {attempt+1}/{max_retries})")
                        time.sleep(sleep_time)
                    else:
                        logger.error(f"Error in LLM verification (Attempt {attempt+1}): {e}")
                        if attempt == max_retries - 1:
                            logger.warning(f"Skipping batch due to persistent error: {e}")

            # Proactive rate limiting for Flash-Lite (15 RPM = 1 req / 4s)
            # Adding a small buffer to be safe
            time.sleep(4.5)

        return verified_groups

    def _ensure_spacy_model(self):
        if not hasattr(self, "_nlp"):
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("Spacy model 'en_core_web_sm' not found. Downloading...")
                from spacy.cli import download

                download("en_core_web_sm")
                self._nlp = spacy.load("en_core_web_sm")
        return self._nlp

    def _predict_structured(self, prompt_tmpl: PromptTemplate, **kwargs) -> Any:
        if hasattr(self.llm, "structured_predict"):
            return self.llm.structured_predict(EntityVerificationBatch, prompt=prompt_tmpl, **kwargs)
        else:
            program = LLMTextCompletionProgram.from_defaults(output_cls=EntityVerificationBatch, prompt=prompt_tmpl, llm=self.llm, verbose=False)
            return program(**kwargs)
