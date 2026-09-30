import re
import unicodedata


CANONICAL_SANTO_DOMINGO_SECTORS = (
    "24 de Abril",
    "30 de Mayo",
    "Altos de Arroyo Hondo",
    "Arroyo Manzano",
    "Atala",
    "Bella Vista",
    "Buenos Aires",
    "El Cacique",
    "Centro de los Héroes",
    "Centro Olímpico",
    "Cerros de Arroyo Hondo",
    "Ciudad Colonial",
    "Ciudad Nueva",
    "Ciudad Universitaria",
    "Cristo Rey",
    "Domingo Savio",
    "El Millón",
    "Ensanche Capotillo",
    "Ensanche Espaillat",
    "Ensanche La Fe",
    "Ensanche Luperón",
    "Naco",
    "Ensanche Quisqueya",
    "Gascue",
    "General Antonio Duvergé",
    "Gualey",
    "Honduras del Norte",
    "Honduras del Oeste",
    "Jardín Botánico",
    "Jardín Zoológico",
    "Jardines del Sur",
    "Julieta Morales",
    "La Agustina",
    "La Castellana",
    "La Esperilla",
    "La Hondonada",
    "La Isabela",
    "La Julia",
    "Las Praderas",
    "La Zurza",
    "Los Cacicazgos",
    "Los Jardines",
    "Los Peralejos",
    "Los Prados",
    "Los Restauradores",
    "Los Ríos",
    "María Auxiliadora",
    "Mata Hambre",
    "Mejoramiento Social",
    "Mirador Norte",
    "Mirador Sur",
    "Miraflores",
    "Miramar",
    "Nuestra Señora de la Paz",
    "Nuevo Arroyo Hondo",
    "Palma Real",
    "Paraíso",
    "Paseo de los Indios",
    "Piantini",
    "Los Próceres",
    "Renacimiento",
    "San Carlos",
    "San Diego",
    "San Gerónimo",
    "San Juan Bosco",
    "Simón Bolívar",
    "Viejo Arroyo Hondo",
    "Villas Agrícolas",
    "Villa Consuelo",
    "Villa Francisca",
    "Villa Juana",
    "Alfimar",
    "Altos De Arroyo Hondo II",
    "Altos de Arroyo Hondo III",
    "Autopista Duarte",
    "Av. Anacaona",
    "Av. Cayetano Germosén",
    "Av. George Washington",
    "Av. Independencia",
    "Av. Máximo Gómez",


)

def sector_lookup_key(value):
    normalized_value = unicodedata.normalize(
        "NFKD",
        value,
    )

    ascii_value = (
        normalized_value.encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
    )

    return " ".join(ascii_value.split())


CANONICAL_SECTORS_BY_KEY = {
    sector_lookup_key(sector): sector
    for sector in CANONICAL_SANTO_DOMINGO_SECTORS
}

SECTOR_ALIASES = {
    "Ensanche Naco": "Naco",
    "Bella Vista Sur": "Bella Vista",
    "Ensanche Gascue": "Gascue",
    "Ensanche Julieta Morales": "Julieta Morales",
    "Ensanche Piantini": "Piantini",
    "Arroyo Hondo Viejo": "Viejo Arroyo Hondo",
}

SECTOR_ALIASES_BY_KEY = {
    sector_lookup_key(alias): canonical_sector 
    for alias, canonical_sector in SECTOR_ALIASES.items()
}

def canonicalize_sector(value):
    cleaned_value = " ".join(value.strip().split())
    lookup_key = sector_lookup_key(cleaned_value)

    return SECTOR_ALIASES_BY_KEY.get(
        lookup_key,
        CANONICAL_SECTORS_BY_KEY.get(
            lookup_key,
            cleaned_value,
        ),
    )

SUPERCASAS_SLUG_OVERRIDES = {
    "Naco": "ensanche-naco",
    "Viejo Arroyo Hondo": "arroyo-hondo-viejo",
}


def sector_to_slug(sector):

    if sector in SUPERCASAS_SLUG_OVERRIDES:
        return SUPERCASAS_SLUG_OVERRIDES[sector]

    
    normalized_value = unicodedata.normalize(
        "NFKD",
        sector,
    )

    ascii_value = (
        normalized_value.encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )

    return re.sub(
        r"[^a-z0-9]+",
        "-",
        ascii_value,
    ).strip("-")


SUPERCASAS_SECTOR_SLUGS = tuple(
    sector_to_slug(sector)
    for sector in CANONICAL_SANTO_DOMINGO_SECTORS
)