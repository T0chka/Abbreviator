import pandas as pd
from rapidfuzz import fuzz

SIMILARITY_THRESHOLD = 75

def are_similar(str1, str2, threshold=SIMILARITY_THRESHOLD):
    """
    Returns True if str1 and str2 are considered 'the same' 
    based on the fuzzy ratio threshold.
    """
    ratio = fuzz.ratio(str1.lower(), str2.lower())
    return ratio >= threshold

def cluster_descriptions(descriptions, threshold=SIMILARITY_THRESHOLD):
    """
    Given a list of descriptions, cluster those that are similar.
    Returns:
      - canonical_descriptions: A list of representative strings, one per cluster.
      - merged_map: A dictionary mapping each original description to
        the representative (canonical) description of its cluster.
    """
    clusters = []       # e.g., [ ["descA", "descB"], ["descC"] ]
    merged_map = {}     # e.g., { "descA": "descA", "descB": "descA", "descC": "descC" }

    for desc in descriptions:
        matched_cluster = None
        for cluster in clusters:
            # Compare with one representative from the cluster (cluster[0]) to see if desc belongs here
            if are_similar(desc, cluster[0], threshold=threshold):
                cluster.append(desc)
                matched_cluster = cluster
                break
        if not matched_cluster:
            clusters.append([desc])

    # Decide how to pick the 'canonical' description for each cluster.
    # Here, we'll simply use cluster[0] as the canonical one.
    canonical_descriptions = []
    for cluster in clusters:
        representative = cluster[0]
        canonical_descriptions.append(representative)
        for item in cluster:
            merged_map[item] = representative

    return canonical_descriptions, merged_map

df = pd.read_csv("data/abb_dict_review.csv")
df['abbreviation'] = df['abbreviation'].str.strip()
grouped = df.groupby('abbreviation')['description'].apply(lambda x: sorted(set(x)))

original_rows = len(df)
unique_pairs = df.drop_duplicates(['abbreviation', 'description']).shape[0]

final_records = [] 
details_per_abbrev = {}

for abbreviation, description_list in grouped.items():
        canonical_descriptions, merged_map = cluster_descriptions(description_list, SIMILARITY_THRESHOLD)
        # Add final (abbreviation, canonical_desc) pairs
        for desc in canonical_descriptions:
            final_records.append((abbreviation, desc))

        # Store details for potential printing
        details_per_abbrev[abbreviation] = {
            "original_descriptions": description_list,
            "canonical_descriptions": canonical_descriptions,
            "merged_map": merged_map
        }

result_df = pd.DataFrame(final_records, columns=['abbreviation', 'description'])
result_df.sort_values(by=['abbreviation', 'description'], inplace=True)

result_df.to_csv("data/abb_dict_cleaned.csv", index=False, encoding='utf-8-sig')

print("Done! Cleaned data saved to abbreviations_cleaned.csv")


print("===========================================")
print(f"Original rows in CSV: {original_rows}")
print(f"Unique (Abbreviation, Description) pairs: {unique_pairs}")
print(f"Rows after merging: {len(result_df)}")
print("===========================================")

# Print per-abbreviation details:
for abb, info in details_per_abbrev.items():
    original_descs = info["original_descriptions"]
    can_descs = info["canonical_descriptions"]

    # Condition: Only print if merges actually happened.
    # That is, there were multiple original descriptions,
    # and the final (canonical) count is strictly less than the original.
    if len(original_descs) > 1 and len(can_descs) < len(original_descs):
        print(f"\nAbbreviation: {abb}")
        print(f"  - Original unique descriptions: {original_descs}")
        print(f"  - Formed {len(can_descs)} cluster(s).")

        # Print details about each cluster
        merged_map = info["merged_map"]
        for cdesc in can_descs:
            # Show which original descriptions ended up in this cluster
            originals_in_cluster = [od for od in original_descs if merged_map[od] == cdesc]
            print(f"      * Canonical: {cdesc}")
            print(f"        -> {originals_in_cluster}")
