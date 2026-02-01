from sqlalchemy import create_engine, Column, Integer, DateTime, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.declarative import declarative_base
import os
from datetime import datetime
import time

from .models import Base, Pokemon, Type, PokemonType, Ability, PokemonAbility, Region, Move, PokemonMove
from .api import get_regions, get_all_pokemon_species_names, get_pokemon_details, get_type_details, get_ability_details, get_move_details, get_species_details, get_species_varieties
from ..config import DATABASE_PATH

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    execution_options={"isolation_level": "AUTOCOMMIT"}
)
# Optimize SQLite performance
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Define a simple model for synchronization information
class SyncInfo(Base):
    __tablename__ = "sync_info"
    id = Column(Integer, primary_key=True)
    last_sync = Column(DateTime, default=datetime.now)
    status = Column(String, default="success")

    def __repr__(self):
        return f"<SyncInfo(last_sync=\'{self.last_sync}\', status=\'{self.status}\')>"

def init_db():
    """Initializes the database by creating all tables and performs initial sync if needed."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at {DATABASE_PATH}")
    sync_database()

def get_db():
    """Dependency for getting a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_session():
    """Provides a new database session directly without a generator."""
    return SessionLocal()

def add_to_db(session, item, commit=True):
    """Helper function to add an item to the database session."""
    try:
        session.add(item)
        if commit:
            session.commit()
            session.refresh(item)
        return item
    except IntegrityError:
        session.rollback()
        return None
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Error adding item to DB: {e}")
        return None

def add_all_to_db(session, items, commit=True):
    """Helper function to add multiple items to the database session."""
    try:
        session.add_all(items)
        if commit:
            session.commit()
            for item in items:
                session.refresh(item)
        return items
    except IntegrityError:
        session.rollback()
        return None
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Error adding items to DB: {e}")
        return None

def is_pokemon_data_complete(pokemon):
    """Checks if a Pokemon has all its critical data fields."""
    if not pokemon:
        return False
    
    # Check basic fields
    critical_fields = [
        pokemon.description,
        pokemon.height,
        pokemon.weight,
        pokemon.sprite_url,
        pokemon.artwork_url,
        pokemon.hp,
        pokemon.attack,
        pokemon.defense,
        pokemon.special_attack,
        pokemon.special_defense,
        pokemon.speed
    ]
    
    if any(field is None for field in critical_fields):
        return False
    
    # Check relationships
    if not pokemon.types:
        return False
    if not pokemon.abilities:
        return False
    if not pokemon.moves:
        return False
    if not pokemon.region:
        return False
        
    return True

def update_pokemon_data(session, pokemon_id, pokemon_url=None, name=None):
    """Fetches and updates data for a specific Pokemon by ID."""
    
    pokemon = session.query(Pokemon).filter_by(id=pokemon_id).first()
    
    # If we already have the basic info and we are just "synching", we can skip the deep fetch
    # unless we explicitly want to force update.
    # For now, let's assume if it exists, we only update if it's incomplete.
    
    if pokemon and is_pokemon_data_complete(pokemon):
        return pokemon

    print(f"Updating/Fetching full data for Pokemon {name or pokemon_id}...")
    
    # If pokemon_url is not provided, we might need to derive it or use name if we had it
    # But get_pokemon_details can take name_or_id
    pokemon_details = get_pokemon_details(name_or_id=pokemon_id, pokemon_url=pokemon_url)
    if not pokemon_details:
        print(f"Failed to fetch details for Pokemon ID {pokemon_id}")
        return None
    
    # If pokemon doesn't exist, it will be created below
    # If it exists, we update its fields
    
    region_name_from_details = pokemon_details.get("region_name")
    pokemon_region = None
    if region_name_from_details:
        pokemon_region = session.query(Region).filter_by(name=region_name_from_details).first()
        if not pokemon_region:
            pokemon_region = Region(name=region_name_from_details)
            add_to_db(session, pokemon_region)

    if not pokemon:
        pokemon = Pokemon(id=pokemon_id)
        session.add(pokemon)

    # Update fields
    pokemon.name = pokemon_details["name"]
    pokemon.form_name = pokemon_details.get("form_name", "")
    pokemon.description = pokemon_details.get("description", "No description available.")
    pokemon.height = pokemon_details["height"]
    pokemon.weight = pokemon_details["weight"]
    pokemon.base_experience = pokemon_details.get("base_experience")
    pokemon.sprite_url = pokemon_details["sprites"]["front_default"]
    pokemon.artwork_url = pokemon_details["sprites"]["other"]["official-artwork"]["front_default"]
    pokemon.cry_url = pokemon_details.get("cry_url")
    pokemon.is_legendary = pokemon_details.get("is_legendary", False)
    pokemon.is_mythical = pokemon_details.get("is_mythical", False)
    pokemon.species_url = pokemon_details.get("species_url")
    pokemon.evolution_chain_url = pokemon_details.get("evolution_chain_url")
    pokemon.hp = pokemon_details.get("hp")
    pokemon.attack = pokemon_details.get("attack")
    pokemon.defense = pokemon_details.get("defense")
    pokemon.special_attack = pokemon_details.get("sp_attack")
    pokemon.special_defense = pokemon_details.get("sp_defense")
    pokemon.speed = pokemon_details.get("speed")
    pokemon.region = pokemon_region

    # Update types
    session.query(PokemonType).filter_by(pokemon_id=pokemon.id).delete()
    for type_entry in pokemon_details["types"]:
        type_name = type_entry["type"]["name"]
        type_obj = session.query(Type).filter_by(name=type_name).first()
        if not type_obj:
            type_obj = Type(name=type_name)
            session.add(type_obj)
            session.flush()
        session.add(PokemonType(pokemon=pokemon, type=type_obj))

    # Update abilities
    session.query(PokemonAbility).filter_by(pokemon_id=pokemon.id).delete()
    for ability_entry in pokemon_details["abilities"]:
        ability_name = ability_entry["ability"]["name"]
        ability = session.query(Ability).filter_by(name=ability_name).first()
        if not ability:
            ability_details = get_ability_details(ability_name)
            description = "No description."
            short_description = "No description."
            if ability_details and "effect_entries" in ability_details:
                for entry in ability_details["effect_entries"]:
                    if entry["language"]["name"] == "en":
                        description = entry["effect"]
                        short_description = entry["short_effect"]
                        break
            ability = Ability(name=ability_name, description=description, short_description=short_description)
            session.add(ability)
            session.flush()
        session.add(PokemonAbility(pokemon=pokemon, ability=ability, is_hidden=ability_entry.get("is_hidden", False), slot=ability_entry.get("slot")))

    # Update moves
    session.query(PokemonMove).filter_by(pokemon_id=pokemon.id).delete()
    for move_entry in pokemon_details.get("detailed_moves", []):
        move_name = move_entry["name"]
        move = session.query(Move).filter_by(name=move_name).first()
        if not move:
            move_details = get_move_details(move_name)
            if move_details:
                move_type_name = move_details["type"]["name"]
                move_type_obj = session.query(Type).filter_by(name=move_type_name).first()
                if not move_type_obj:
                    move_type_obj = Type(name=move_type_name)
                    session.add(move_type_obj)
                    session.flush()
                move = Move(
                    id=move_details["id"],
                    name=move_details["name"],
                    power=move_details["power"],
                    pp=move_details["pp"],
                    accuracy=move_details["accuracy"],
                    damage_class=move_details["damage_class"]["name"],
                    effect_chance=move_details.get("effect_chance"),
                    description=move_details["effect_entries"][0]["effect"] if move_details["effect_entries"] else "No description.",
                    type=move_type_obj
                )
                session.add(move)
                session.flush()
        if move:
            session.add(PokemonMove(
                pokemon=pokemon,
                move=move,
                learn_method=move_entry.get("learn_method", "unknown"),
                level_learned_at=move_entry.get("level_learned_at", 0),
                version_group=move_entry.get("version_group", "unknown")
            ))
    
    session.commit()
    session.refresh(pokemon)
    return pokemon

def sync_database(background=False, progress_callback=None):
    print("Starting database synchronization...")
    session = get_session()
    try:
        sync_info = session.query(SyncInfo).first()
        if not sync_info:
            print("No sync info found, performing initial full sync.")
            sync_info = SyncInfo(last_sync=datetime.min, status="in_progress")
            session.add(sync_info)
            session.commit()
            session.refresh(sync_info)
        else:
            print(f"Last sync: {sync_info.last_sync}. Checking for updates...")

        # Optimization: Check if we have any pokemon at all
        pokemon_count = session.query(Pokemon).count()
        if pokemon_count == 0:
            print("Database is empty, performing full synchronization.")
        
        print("Performing database synchronization.")

        # Step 1: Fetch and store all regions
        regions_data = get_regions()
        regions_to_add = []
        for region_entry in regions_data:
            region_name = region_entry["name"]
            existing_region = session.query(Region).filter_by(name=region_name).first()
            if not existing_region:
                regions_to_add.append(Region(name=region_name))
                print(f"Added region: {region_name}")
        if regions_to_add:
            add_all_to_db(session, regions_to_add)

        # Step 2: Fetch all Pokemon species names (this is just one request for ~1000 names)
        all_pokemon_species = get_all_pokemon_species_names()
        
        # Check if we already have these species in our DB as basic entries
        # For a truly fast startup, we only want to ensure the list is populated.
        # Deep data (stats, moves, varieties like Mega/G-Max) should be fetched on demand.
        
        print(f"Syncing {len(all_pokemon_species)} species...")

        # Pre-fetch existing IDs to avoid repeated queries
        existing_ids = {row[0] for row in session.query(Pokemon.id).all()}
        
        new_pokemon_stubs = []
        total_species = len(all_pokemon_species)
        for i, species_entry in enumerate(all_pokemon_species):
            if background and progress_callback:
                if i % 100 == 0:
                    progress_callback(i, total_species)
            species_url = species_entry["url"]
            try:
                species_id = int(species_url.split("/")[-2])
                if species_id not in existing_ids:
                    new_pokemon_stubs.append(Pokemon(
                        id=species_id,
                        name=species_entry["name"],
                        species_url=species_url,
                        sprite_url=f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{species_id}.png"
                    ))
            except (ValueError, IndexError):
                continue

        if new_pokemon_stubs:
            # Batch add for performance
            for i in range(0, len(new_pokemon_stubs), 500):
                batch = new_pokemon_stubs[i:i+500]
                session.add_all(batch)
                session.commit()

        # Step 3: Deep sync - Fetch full data for all pokemon that are incomplete
        if background:
            print("Performing deep synchronization for all Pokémon...")
            # Re-fetch all pokemon to check completeness
            # We do this in batches to avoid keeping too many objects in memory
            all_pokemon = session.query(Pokemon).all()
            total_to_deep_sync = len(all_pokemon)
            
            for i, pokemon in enumerate(all_pokemon):
                if not is_pokemon_data_complete(pokemon):
                    # update_pokemon_data handles its own session.commit()
                    update_pokemon_data(session, pokemon.id, name=pokemon.name)
                
                if progress_callback and i % 10 == 0:
                    progress_callback(i, total_to_deep_sync)

        sync_info.last_sync = datetime.now()
        sync_info.status = "success"
        session.add(sync_info)
        session.commit()
        print("Database synchronization completed successfully.")

    except SQLAlchemyError as e:
        session.rollback()
        sync_info.status = f"failed: {e}"
        session.add(sync_info)
        session.commit()
        print(f"Database synchronization failed: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    init_db()
