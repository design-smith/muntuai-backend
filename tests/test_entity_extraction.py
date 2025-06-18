import sys
import os
import pytest
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.GraphRAG.graphrag.engine.entity_extraction import EntityExtractor

@pytest.fixture(scope="module")
def extractor():
    return EntityExtractor()

def test_entity_extraction_basic(extractor):
    text = """
    Hi John,
    Please schedule a meeting with Alice from Acme Corp at our New York office next week. You can reach her at alice@acme.com or +1 (555) 123-4567. The agenda is to discuss the Q2 budget.
    Regards,
    Bob
    """
    entities = extractor.extract_entities(text)
    print("Extracted entities:")
    for e in entities:
        print(e)
    assert any(e['type'] == 'Person' and 'Alice' in e['text'] for e in entities)
    assert any(e['type'] == 'Organization' and 'Acme' in e['text'] for e in entities)
    assert any(e['type'] == 'Location' and 'New York' in e['text'] for e in entities)
    assert any(e['type'] == 'ContactInfo' and '@acme.com' in e['text'] for e in entities)
    assert any(e['type'] == 'ContactInfo' and '555' in e['text'] for e in entities)

def test_entity_deduplication(extractor):
    text = "Alice met Alice at Acme Corp. Alice is from Acme Corp."
    entities = extractor.extract_entities(text)
    print("Deduplicated entities:")
    for e in entities:
        print(e)
    # Should only have one Alice and one Acme Corp
    assert sum(1 for e in entities if e['type'] == 'Person' and 'Alice' in e['text']) == 1
    assert sum(1 for e in entities if e['type'] == 'Organization' and 'Acme' in e['text']) == 1

def test_relationship_extraction(extractor):
    text = "Alice from Acme Corp visited New York."
    entities = extractor.extract_entities(text)
    relationships = extractor.extract_relationships(text, entities)
    print("Extracted relationships:")
    for r in relationships:
        print(r)
    assert any(r['relationship_type'] == 'AFFILIATED_WITH' for r in relationships)
    assert any(r['relationship_type'] == 'LOCATED_AT' for r in relationships)

def test_multiple_entities_same_sentence(extractor):
    text = "Bob and Alice from Acme Corp went to Paris."
    entities = extractor.extract_entities(text)
    relationships = extractor.extract_relationships(text, entities)
    print("Entities:")
    for e in entities:
        print(e)
    print("Relationships:")
    for r in relationships:
        print(r)
    # Should find both affiliation and location relationships
    rel_types = [r['relationship_type'] for r in relationships]
    assert 'AFFILIATED_WITH' in rel_types or 'HAS_MEMBER' in rel_types
    assert 'LOCATED_AT' in rel_types

def test_no_false_positives(extractor):
    text = "The quick brown fox jumps over the lazy dog."
    entities = extractor.extract_entities(text)
    print("Entities in neutral text:", entities)
    assert len(entities) == 0 