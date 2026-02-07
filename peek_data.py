import pandas as pd
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()
FILE_PATH = Path("data/result/candidates_reranked.parquet")

def peek_parquet():
    if not FILE_PATH.exists():
        console.print(f"[red]❌ File not found: {FILE_PATH}[/red]")
        return

    # Load only the first 5 rows to keep it fast
    df = pd.read_parquet(FILE_PATH).head(5)

    # Create a Rich table for terminal display
    table = Table(title=f"📊 Parquet Peek: {FILE_PATH.name}", header_style="bold magenta")

    # Add Columns (Headers)
    for column in df.columns:
        table.add_column(column, overflow="ellipsis")

    # Add Rows (Sample Data)
    for _, row in df.iterrows():
        table.add_row(*[str(val)[:5] for val in row.values])

    console.print(table)
    
    # Print Column List explicitly for easy copying
    console.print(f"\n[bold cyan]Headers Found:[/bold cyan] {list(df.columns)}")
    console.print(f"[bold cyan]Total Candidates:[/bold cyan] {len(pd.read_parquet(FILE_PATH))}")

if __name__ == "__main__":
    peek_parquet()