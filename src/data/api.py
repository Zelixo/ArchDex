import requests
import json
from functools import lru_cache

POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"

# Use a session for connection pooling
session = requests.Session()

@lru_cache(maxsize=1024)
def _fetch_data(url):
    try:
        response = session.get(url, timeout=5)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return None

def get_regions():
    url = f"{POKEAPI_BASE_URL}/region?limit=100"  # A reasonably high limit to get all regions
    data = _fetch_data(url)
    return data["results"] if data else []

def get_region_details(name_or_id):
    url = f"{POKEAPI_BASE_URL}/region/{name_or_id}/"
    return _fetch_data(url)

def get_all_pokemon_species_names():
    # Get a list of all pokemon species from the API. Use a high limit.
    url = f"{POKEAPI_BASE_URL}/pokemon-species?limit=10000"  # Fetch all species
    data = _fetch_data(url)
    return data["results"] if data else []

def get_species_varieties(species_url):
    species_data = _fetch_data(species_url)
    if species_data and "varieties" in species_data:
        return species_data["varieties"]
    return []

def get_pokemon_list_by_region(region_url):
    # This function is no longer actively used in sync_database but kept for completeness
    region_data = _fetch_data(region_url)
    if not region_data or "main_generation" not in region_data or not region_data["main_generation"]:
        return []
    
    gen_data = _fetch_data(region_data["main_generation"]["url"])
    if not gen_data or "pokemon_species" not in gen_data:
        return []
    
    return gen_data["pokemon_species"]

def get_pokemon_details(name_or_id=None, pokemon_url=None):
    if pokemon_url:
        url = pokemon_url
    elif name_or_id:
        url = f"{POKEAPI_BASE_URL}/pokemon/{name_or_id}/"
    else:
        return None

    pokemon_data = _fetch_data(url)
    if not pokemon_data:
        return None

    # Derive form_name from the pokemon_data["name"]
    # The format is often "pokemon-name-form-name" (e.g., "charizard-mega-x")
    # Or sometimes just "pokemon-name" for default forms
    full_name = pokemon_data["name"]
    # Need to fetch species data early to get base_name for form derivation
    species_data_for_name_derive = _fetch_data(pokemon_data["species"]["url"])
    if species_data_for_name_derive:
        base_name = species_data_for_name_derive["name"]
        form_name = full_name.replace(base_name, "").strip("-")
        pokemon_data["form_name"] = form_name if form_name else ""
    else:
        pokemon_data["form_name"] = ""

    # Fetch species data for description, legendary/mythical status, and region
    # Re-fetch species data or use existing if it's the same URL
    species_url = pokemon_data["species"]["url"]
    species_data = _fetch_data(species_url)

    if species_data:
        pokemon_data["description"] = get_pokemon_description(species_data)
        pokemon_data["is_legendary"] = species_data.get("is_legendary", False)
        pokemon_data["is_mythical"] = species_data.get("is_mythical", False)
        pokemon_data["species_url"] = species_url
        pokemon_data["evolution_chain_url"] = species_data.get("evolution_chain", {}).get("url")
        # Extract region from species data
        if "generation" in species_data and species_data["generation"]:
            gen_data = _fetch_data(species_data["generation"]["url"])
            if gen_data and "main_region" in gen_data and gen_data["main_region"]:
                pokemon_data["region_name"] = gen_data["main_region"]["name"]
            else:
                pokemon_data["region_name"] = None
        else:
            pokemon_data["region_name"] = None
    else:
        pokemon_data["description"] = "No description available."
        pokemon_data["is_legendary"] = False
        pokemon_data["is_mythical"] = False
        pokemon_data["species_url"] = species_url
        pokemon_data["region_name"] = None

    # Fetch moves details - only storing move names for now, full details can be fetched on demand
    moves_data = []
    for move_entry in pokemon_data.get("moves", []):
        move_name = move_entry["move"]["name"]
        move_url = move_entry["move"]["url"]
        
        # De-duplicate moves per version group
        # Version groups like "red-blue" already represent multiple versions
        # but sometimes the API might have redundant entries or we want to ensure
        # we only store one entry per move/method/level/version_group
        seen_moves_in_pokemon = set()
        for version_detail in move_entry.get("version_group_details", []):
            move_key = (
                move_name,
                version_detail["move_learn_method"]["name"],
                version_detail["level_learned_at"],
                version_detail["version_group"]["name"]
            )
            if move_key not in seen_moves_in_pokemon:
                moves_data.append({
                    "name": move_name,
                    "url": move_url,
                    "learn_method": version_detail["move_learn_method"]["name"],
                    "level_learned_at": version_detail["level_learned_at"],
                    "version_group": version_detail["version_group"]["name"]
                })
                seen_moves_in_pokemon.add(move_key)
    pokemon_data["detailed_moves"] = moves_data  # Storing in a new key to avoid conflicts

    # Extract base stats
    # For Gen 1 Pokemon, PokeAPI returns the special stat in both 'special-attack' and 'special-defense'
    # but we want to ensure we're using the split stats which are correctly populated in PokeAPI
    # for all pokemon since Gen 2.
    for stat_entry in pokemon_data.get("stats", []):
        stat_name = stat_entry["stat"]["name"].replace("special-", "sp_")  # e.g., hp, attack, defense, sp_attack, sp_defense, speed
        pokemon_data[stat_name] = stat_entry["base_stat"]

    # Extract cries
    pokemon_data["cry_url"] = pokemon_data.get("cries", {}).get("latest")

    return pokemon_data

@lru_cache(maxsize=64)
def get_type_details(name_or_id):
    url = f"{POKEAPI_BASE_URL}/type/{name_or_id}/"
    return _fetch_data(url)

@lru_cache(maxsize=128)
def get_ability_details(name_or_id):
    url = f"{POKEAPI_BASE_URL}/ability/{name_or_id}/"
    return _fetch_data(url)

@lru_cache(maxsize=256)
def get_move_details(name_or_id):
    url = f"{POKEAPI_BASE_URL}/move/{name_or_id}/"
    return _fetch_data(url)

@lru_cache(maxsize=128)
def get_species_details(name_or_id):
    url = f"{POKEAPI_BASE_URL}/pokemon-species/{name_or_id}/"
    return _fetch_data(url)

def get_pokemon_description(species_data):
    for entry in species_data["flavor_text_entries"]:
        if entry["language"]["name"] == "en":
            return entry["flavor_text"].replace("\n", " ").replace("\f", " ")
    return "No description available."
