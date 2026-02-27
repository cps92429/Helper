import argparse
import os
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class Summary:
    sheets: int
    rows_total: int
    cols_max: int


def summarize_excel(path: str) -> Summary:
    xl = pd.ExcelFile(path)
    rows_total = 0
    cols_max = 0
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        rows_total += int(df.shape[0])
        cols_max = max(cols_max, int(df.shape[1]))
    return Summary(sheets=len(xl.sheet_names), rows_total=rows_total, cols_max=cols_max)


def write_summary(path: str, output_dir: str) -> str:
    s = summarize_excel(path)
    base = os.path.splitext(os.path.basename(path))[0]
    out_path = os.path.join(output_dir, f"{base}.summary.csv")
    os.makedirs(output_dir, exist_ok=True)
    pd.DataFrame(
        [
            {
                "file": os.path.basename(path),
                "sheets": s.sheets,
                "rows_total": s.rows_total,
                "cols_max": s.cols_max,
            }
        ]
    ).to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path


def automanage_excel(path: str, output_dir: str, visible: bool = False) -> str:
    """
    Best-effort "auto manage":
    - Create a copy in output_dir
    - If Excel is installed, use COM to auto-fit columns and freeze top row
    """
    base = os.path.splitext(os.path.basename(path))[0]
    out_path = os.path.join(output_dir, f"{base}.managed.xlsx")
    os.makedirs(output_dir, exist_ok=True)

    # Copy first (ensures we never mutate input file).
    with open(path, "rb") as src, open(out_path, "wb") as dst:
        dst.write(src.read())

    try:
        import win32com.client  # type: ignore

        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = bool(visible)
        wb = excel.Workbooks.Open(os.path.abspath(out_path))
        try:
            for ws in wb.Worksheets:
                ws.Activate()
                ws.Rows(1).Font.Bold = True
                ws.Application.ActiveWindow.SplitRow = 1
                ws.Application.ActiveWindow.FreezePanes = True
                ws.Columns.AutoFit()
            wb.Save()
        finally:
            wb.Close(SaveChanges=True)
            excel.Quit()
    except Exception:
        # If Excel/COM isn't available, keep the copied file.
        pass

    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, choices=["excel.summarize", "excel.automanage"])
    parser.add_argument("--input", required=True, help="Path to .xlsx")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--visible", action="store_true", help="Show Excel UI (automanage only)")
    args = parser.parse_args()

    if args.task == "excel.summarize":
        out = write_summary(args.input, args.output_dir)
        print(out)
        return 0

    out = automanage_excel(args.input, args.output_dir, visible=bool(args.visible))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

