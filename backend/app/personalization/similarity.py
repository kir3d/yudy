def similarity(left, right):
    matches = [
        bool(left[key] and left[key] == right[key])
        for key in ("sector", "industry", "region", "country", "asset_type")
    ]
    matches.append(bool(set(left["themes"]) & set(right["themes"])))
    return sum(matches) / len(matches)
