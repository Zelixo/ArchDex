
from src.data.database import get_session, is_pokemon_data_complete, update_pokemon_data, init_db, engine
from src.data.models import Pokemon, Base

def test_robust_update():
    # Initialize DB (create tables)
    Base.metadata.create_all(bind=engine)
    
    session = get_session()
    try:
        # 1. Manually create an incomplete Pokemon entry
        # We'll use a real ID but omit fields
        test_id = 1 # Bulbasaur
        
        # Clear existing if any (be careful with real db, but this is for testing)
        existing = session.query(Pokemon).filter_by(id=test_id).first()
        if existing:
            print(f"Removing existing Pokemon {test_id} for test")
            session.delete(existing)
            session.commit()
            
        incomplete_pokemon = Pokemon(id=test_id, name="bulbasaur-incomplete")
        session.add(incomplete_pokemon)
        session.commit()
        
        print(f"Created incomplete Pokemon: {incomplete_pokemon}")
        
        # 2. Check completeness
        is_complete = is_pokemon_data_complete(incomplete_pokemon)
        print(f"Is complete (should be False): {is_complete}")
        assert is_complete == False
        
        # 3. Trigger update
        updated_pokemon = update_pokemon_data(session, test_id)
        
        # 4. Check completeness again
        is_complete_now = is_pokemon_data_complete(updated_pokemon)
        print(f"Is complete after update (should be True): {is_complete_now}")
        assert is_complete_now == True
        print(f"Updated Pokemon name: {updated_pokemon.name}")
        print(f"Updated Pokemon description: {updated_pokemon.description[:50]}...")
        
    finally:
        session.close()

if __name__ == "__main__":
    test_robust_update()
