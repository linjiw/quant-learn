from quant_learn.db import initialize_database


def main() -> None:
    initialize_database()
    print("Initialized DuckDB schema.")


if __name__ == "__main__":
    main()
