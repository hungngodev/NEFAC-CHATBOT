from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd
from unstructured.partition.auto import partition as u_partition


def process_xlsx_intelligently(file_path: str, entry: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    try:
        excel_file = pd.ExcelFile(file_path)
        chunks: List[Tuple[str, Dict[str, Any]]] = []

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)

            if df.empty:
                continue

            df = df.dropna(how="all").dropna(axis=1, how="all")

            if df.empty:
                continue

            headers = [str(col).strip() for col in df.columns]
            total_rows = len(df)

            sheet_text = f"Sheet: {sheet_name}\nColumns: {', '.join(headers)}\n\n"

            for idx, row in df.iterrows():
                row_data = [f"{header}: {str(value).strip()}" for header, value in zip(headers, row) if pd.notna(value) and str(value).strip()]

                if row_data:
                    sheet_text += f"Row {idx + 1}: {' | '.join(row_data)}\n"

            chunk_metadata = {
                "document_type": "spreadsheet",
                "spreadsheet_format": "xlsx",
                "sheet_name": sheet_name,
                "total_rows": total_rows,
                "headers": headers,
                "processing_method": "intelligent_sheet_conversion",
            }

            chunks.append((sheet_text.strip(), chunk_metadata))

        if chunks:
            return chunks

        return [
            (
                "Empty spreadsheet with no processable data.",
                {
                    "document_type": "spreadsheet",
                    "spreadsheet_format": "xlsx",
                    "processing_method": "empty",
                },
            )
        ]

    except Exception:
        try:
            elements = u_partition(file_path)
            text = "\n\n".join(str(el).strip() for el in elements if str(el).strip())
            return [
                (
                    text,
                    {
                        "document_type": "spreadsheet",
                        "spreadsheet_format": "xlsx",
                        "processing_method": "unstructured_fallback",
                    },
                )
            ]
        except Exception as fallback_error:
            return [
                (
                    "Failed to process spreadsheet content.",
                    {
                        "document_type": "spreadsheet",
                        "spreadsheet_format": "xlsx",
                        "processing_method": "failed",
                        "error": str(fallback_error),
                    },
                )
            ]
