import os
import sys
from pathlib import Path

def test_feature_build():
    """Test the feature building pipeline"""
    result = os.system("python src/feature_build.py")
    assert result == 0, "Feature build failed"

def test_score_and_push():
    """Test the scoring and Notion push pipeline"""
    result = os.system("python src/score_and_push.py")
    assert result == 0, "Score and push failed"

if __name__ == "__main__":
    # Ensure we're in the project root
    os.chdir(Path(__file__).parent.parent)
    
    print("Testing feature build...")
    test_feature_build()
    
    print("Testing score and push...")
    test_score_and_push()
    
    print("All tests passed!")