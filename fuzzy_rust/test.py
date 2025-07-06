import fuzzy_rust


print(
    fuzzy_rust.extract_bests(
        "hi", ["hello", "world", "whatt", "hhhhhhhhhhiiiiiiiiiiiiii"], limit=2
    )
)
