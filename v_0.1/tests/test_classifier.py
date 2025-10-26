"""
Test thermal classifier
"""

import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

# Now we can import as if we're in src/
import detection.thermal_processing as tp
import detection.classifier as classifier_module
import utils.geometry as geometry
import core.state_machine as sm

ThermalBlob = tp.ThermalBlob
ThermalClassifier = classifier_module.ThermalClassifier


def test_classifier():
    """Test person vs boat classification"""
    
    # Mock config
    config = {
        'camera': {
            'fov_horizontal': 51.0,
            'fov_vertical': 38.5,
            'resolution_x': 160,
            'resolution_y': 120
        },
        'detection': {
            'person_temp_min': 30.0,
            'person_temp_max': 37.0,
            'person_size_min': 0.3,
            'person_size_max': 2.0,
            'boat_size_min': 5.0,
            'boat_temp_threshold': 50.0
        }
    }
    
    classifier = ThermalClassifier(config)
    classifier.set_altitude(50.0)
    
    print("Testing Thermal Classifier\n")
    print("="*60)
    
    # Test 1: Person in water
    print("\nTest 1: Person in water")
    person_blob = ThermalBlob(
        center_x=80, center_y=60,
        area=50,  # Small
        mean_temp=33.0,  # Body temp (wet)
        max_temp=36.0,
        min_temp=31.0,
        aspect_ratio=1.2  # Circular
    )
    detection = classifier.classify_blob(person_blob)
    print(f"Result: {detection.target_type.value}")
    print(f"Confidence: {detection.confidence:.2%}")
    assert detection.is_person(), "Should classify as person"
    print("✓ PASS")
    
    # Test 2: Boat with hot engine
    print("\nTest 2: Boat with hot engine")
    boat_blob = ThermalBlob(
        center_x=100, center_y=70,
        area=500,  # Large
        mean_temp=45.0,
        max_temp=85.0,  # Hot engine
        min_temp=25.0,
        aspect_ratio=2.5  # Elongated
    )
    detection = classifier.classify_blob(boat_blob)
    print(f"Result: {detection.target_type.value}")
    print(f"Confidence: {detection.confidence:.2%}")
    assert detection.is_boat(), "Should classify as boat"
    print("✓ PASS")
    
    # Test 3: Debris (ambiguous)
    print("\nTest 3: Debris/Unknown object")
    debris_blob = ThermalBlob(
        center_x=90, center_y=65,
        area=20,  # Too small
        mean_temp=26.0,  # Too cold
        max_temp=28.0,
        min_temp=24.0,
        aspect_ratio=3.0  # Weird shape
    )
    detection = classifier.classify_blob(debris_blob)
    print(f"Result: {detection.target_type.value}")
    print(f"Confidence: {detection.confidence:.2%}")
    assert not detection.is_person() and not detection.is_boat()
    print("✓ PASS")
    
    print("\n" + "="*60)
    print("All tests passed! ✓")


if __name__ == "__main__":
    test_classifier()
