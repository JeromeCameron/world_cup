import json
import os


def dataframe_to_json(df, file_name, orient="records", indent=4):
    """
    Convert a pandas DataFrame to a JSON file.
    """

    # Create folders if they don't exist
    os.makedirs(os.path.dirname(file_name), exist_ok=True)

    # Convert DataFrame to dictionary
    data = df.to_dict(orient=orient)

    # Save JSON file
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)

    print(f"JSON file saved as: {file_name}")


def add_flags_to_json(json_file, flag_dict, output_file=None):
    """
    Loops through a JSON file and adds the correct
    flag image path to the 'flag' field based on country name.

    Parameters:
        json_file (str): Path to input JSON file
        flag_dict (dict): Dictionary with country names as keys
                          and flag image paths as values
        output_file (str): Optional output file path
    """

    # Load JSON data
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Update flag field
    for team in data:
        country = team.get("name")

        if country in flag_dict:
            team["flag"] = flag_dict[country]
        else:
            print(f"No flag found for: {country}")

    # Save updated JSON
    output_path = output_file if output_file else json_file

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"Updated JSON saved to: {output_path}")


if __name__ == "__main__":
    # path = "assets/csv_files/teams.csv"
    # df = pd.read_csv(path, encoding="latin-1")
    file_name = "assets/json/teams.json"
    # dataframe_to_json(df, file_name)

    # add_flags_to_json(file_name, flags)

    # df = pd.read_json("assets/json/groups.json")

    # group_a = df[df["team"] == "Mexico"]
