from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Table

Base = declarative_base()

class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    pokemon = relationship("Pokemon", back_populates="region")

    def __repr__(self):
        return f"<Region(name='{self.name}')>"

class Pokemon(Base):
    __tablename__ = "pokemon"

    id = Column(Integer, primary_key=True, index=True)
    evolution_chain_url = Column(String)
    name = Column(String, index=True)
    description = Column(String)
    form_name = Column(String, default="") # To distinguish between different forms
    height = Column(Float)
    weight = Column(Float)
    base_experience = Column(Integer)
    sprite_url = Column(String)
    artwork_url = Column(String)
    cry_url = Column(String)
    is_legendary = Column(Boolean, default=False)
    is_mythical = Column(Boolean, default=False)
    species_url = Column(String)
    hp = Column(Integer)
    attack = Column(Integer)
    defense = Column(Integer)
    special_attack = Column(Integer)
    special_defense = Column(Integer)
    speed = Column(Integer)

    region_id = Column(Integer, ForeignKey("regions.id"))
    region = relationship("Region", back_populates="pokemon")

    types = relationship("PokemonType", back_populates="pokemon")
    abilities = relationship("PokemonAbility", back_populates="pokemon")
    moves = relationship("PokemonMove", back_populates="pokemon")

    def __repr__(self):
        return f"<Pokemon(name='{self.name}', id={self.id})>"

class Type(Base):
    __tablename__ = "types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    pokemon = relationship("PokemonType", back_populates="type")
    moves = relationship("Move", back_populates="type")

    def __repr__(self):
        return f"<Type(name='{self.name}')>"

class PokemonType(Base):
    __tablename__ = "pokemon_types"

    pokemon_id = Column(Integer, ForeignKey("pokemon.id"), primary_key=True)
    type_id = Column(Integer, ForeignKey("types.id"), primary_key=True)

    pokemon = relationship("Pokemon", back_populates="types")
    type = relationship("Type", back_populates="pokemon")

class Ability(Base):
    __tablename__ = "abilities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    short_description = Column(String)

    pokemon = relationship("PokemonAbility", back_populates="ability")

    def __repr__(self):
        return f"<Ability(name='{self.name}')>"

class PokemonAbility(Base):
    __tablename__ = "pokemon_abilities"

    pokemon_id = Column(Integer, ForeignKey("pokemon.id"), primary_key=True)
    ability_id = Column(Integer, ForeignKey("abilities.id"), primary_key=True)
    is_hidden = Column(Boolean, default=False)
    slot = Column(Integer)

    pokemon = relationship("Pokemon", back_populates="abilities")
    ability = relationship("Ability", back_populates="pokemon")

class Move(Base):
    __tablename__ = "moves"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    power = Column(Integer)
    pp = Column(Integer)
    accuracy = Column(Integer)
    damage_class = Column(String)
    effect_chance = Column(Integer)
    description = Column(String)

    type_id = Column(Integer, ForeignKey("types.id"))
    type = relationship("Type", back_populates="moves")

    pokemon = relationship("PokemonMove", back_populates="move")

    def __repr__(self):
        return f"<Move(name='{self.name}')>"

class PokemonMove(Base):
    __tablename__ = "pokemon_moves"

    pokemon_id = Column(Integer, ForeignKey("pokemon.id"), primary_key=True)
    move_id = Column(Integer, ForeignKey("moves.id"), primary_key=True)
    learn_method = Column(String, primary_key=True)  # level-up, egg, machine, etc.
    level_learned_at = Column(Integer, primary_key=True)
    version_group = Column(String, primary_key=True)

    pokemon = relationship("Pokemon", back_populates="moves")
    move = relationship("Move", back_populates="pokemon")
