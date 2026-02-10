import pandas as pd
import io
import time
import requests
from flask import Flask, jsonify, render_template, redirect
from openpyxl import load_workbook

app = Flask(__name__)

file_name = "next_race_results.csv"
url = f"https://filebin.net/s5al02jenmz68f5l/{file_name}"

@app.route("/")
def home():  
    return render_template("home.html")

@app.route("/report/upcoming-race", methods=["POST"])
def generate_report():
    next_race = get_next_race()
    
    next_race_event_info = next_race["race"][0]

    year = next_race["season"]
    circuit_id = next_race_event_info["circuit"]["circuitId"]
    previous_year_winner_id = get_previous_year_winner(circuit_id, year - 1)

    drivers = get_next_race_teams_and_drivers(year)

    fastest_lap_record_driver_id = next_race_event_info["circuit"]["fastestLapDriverId"]

    current_points_dict = get_current_points_for_drivers(year)

    race_name = next_race_event_info["raceName"]
    race_date = next_race_event_info["schedule"]["race"]["date"]
    circuit_name = next_race_event_info["circuit"]["circuitName"]

    current_points = [current_points_dict[driver["driverId"]] for driver in drivers]
    fastest_lap_driver_bool = [driver["driverId"] == fastest_lap_record_driver_id for driver in drivers]
    previous_year_winner_bool = [driver["driverId"] == previous_year_winner_id for driver in drivers]
    teams = [driver["teamName"] for driver in drivers]
    drivers = [driver["name"] + " " + driver["surname"] for driver in drivers]

    csv_bytes = generate_csv(race_name, year, race_date, circuit_name, teams, drivers, current_points, previous_year_winner_bool, fastest_lap_driver_bool)

    for attempt in range(3):
        response = requests.post(f"{url}", data=csv_bytes)
        if response.status_code == 201:
            return jsonify({"message": "Report uploaded successfully", "filebin_url": url})
        time.sleep(2 ** attempt)  # Wait before retrying
    return jsonify({"error": "Upload failed after retries", "status": response.status_code, "details": response.text}), 500



def get_next_race():
    """
    Get details of next race.
    Returns: Dictionary of details of next race
    """
    next_race = requests.get("https://f1api.dev/api/current/next").json()

    return next_race


def get_previous_year_winner(circuit_id, year):
    """
    Get previous year's winner for the same circuit.
    Args:
        circuit_id (str): Circuit identifier
        year (int): Previous year
    Returns: str driverId of the winner
    """

    winner = ""
    all_race_last_year = requests.get(f"https://f1api.dev/api/{year}").json()
    for race in all_race_last_year["races"]:
        if race["circuit"]["circuitId"] == circuit_id:
            winner = race["winner"]["driverId"]
            break

    return winner

def get_next_race_teams_and_drivers(year):
    """
    Get teams and drivers for the next race.
    Args:
        year (int): The year of the next race
    Returns: list of driver dictionaries with team names
    """

    teams = requests.get(f"https://f1api.dev/api/{year}/teams").json()["teams"]
    drivers = requests.get(f"https://f1api.dev/api/{year}/drivers").json()["drivers"]

    teams_dict = {team["teamId"]: team["teamName"] for team in teams}
    for driver in drivers:
        driver["teamName"] = teams_dict[driver["teamId"]]

    return drivers

def get_current_points_for_drivers(year):
    """
    Get current points for each driver up to next race.
    Args:
        year (int): The year of the next race
    Returns: dictionary of driverId to points
    """

    current_standings = requests.get(f"https://f1api.dev/api/{year}/drivers-championship").json()
    points_dict = {entry["driverId"]: entry["points"] for entry in current_standings["drivers_championship"]}

    return points_dict


def generate_csv(race_name, year, race_date, circuit_name, teams, drivers, current_points, previous_year_winner, fastest_lap_driver):
    number_of_teams = len(teams)
    df = pd.DataFrame({
        "race_name": [race_name]*number_of_teams,
        "year": [year]*number_of_teams,
        "race_date": [race_date]*number_of_teams,
        "circuit_name": [circuit_name]*number_of_teams,
        "team_name": teams,
        "driver_name": drivers,
        "current_points": current_points,
        "previous_year_winner": previous_year_winner,
        "fastest_lap_driver": fastest_lap_driver
    })

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_bytes = csv_buffer.getvalue().encode("utf-8")

    return csv_bytes

if __name__ == "__main__":
    app.run(debug=True)