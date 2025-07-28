from operator import add

from langgraph.graph import END, StateGraph
from langgraph.types import Send
from typing_extensions import Annotated, TypedDict


class TestState(TypedDict):
    characters: Annotated[list[str], add]
    characters_to_generate: list[str]


def generator_node(state: TestState) -> TestState:
    print("Generator: Starting character generation...")
    import time

    time.sleep(1)
    characters_to_add = ["a", "b", "c", "d", "e"]
    print(f"Generator: Generated characters {characters_to_add}")
    return {"characters_to_generate": characters_to_add}


def route_to_add_character(state: TestState) -> list[Send]:
    print("Router: Creating Send commands for parallel execution...")
    characters_to_add = state.get("characters_to_generate", [])
    sends = [Send("add_character", {"character": char}) for char in characters_to_add]
    print(f"Router: Created {len(sends)} Send commands")
    return sends


def add_character_node(state: TestState) -> TestState:
    character = state["character"]
    print(f"Add Character: Processing character '{character}'...")
    import time

    time.sleep(2)
    print(f"Add Character: Completed processing '{character}'")
    return {"characters": [character]}


def collect_results_node(state: TestState) -> TestState:
    print("Collector: Gathering and sorting results...")
    import time

    time.sleep(1)
    chars = state.get("characters", [])
    sorted_chars = sorted(chars)
    print(f"Collector: Final sorted characters: {sorted_chars}")
    return {"characters": sorted_chars}


test_builder = StateGraph(state_schema=TestState)

test_builder.add_node(node="generator", action=generator_node, destinations=["add_character"], metadata={"description": "Generates 5 Send commands for parallel character addition", "type": "generator_node", "parallel_trigger": True, "send_count": 5, "execution_time": "1s"})

test_builder.add_node(node="add_character", action=add_character_node, destinations=["collect_results"], metadata={"description": "Adds a single character to the array", "type": "processing_node", "parallel_execution": True, "execution_time": "2s"})

test_builder.add_node(node="collect_results", action=collect_results_node, destinations=[END], metadata={"description": "Collects and sorts all added characters", "type": "collection_node", "execution_time": "1s"})

test_builder.set_entry_point("generator")
test_builder.add_conditional_edges("generator", route_to_add_character)
test_builder.add_edge("add_character", "collect_results")
test_builder.add_edge("collect_results", END)

test_graph = test_builder.compile(debug=True, name="test_send_commands_graph")
