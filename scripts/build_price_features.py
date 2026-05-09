from quant_learn.analytics.price_features import update_price_return_columns


def main() -> None:
    count = update_price_return_columns()
    print(f"Updated return columns for {count} price rows.")


if __name__ == "__main__":
    main()
