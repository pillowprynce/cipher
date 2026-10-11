import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../artifacts')))
from fizzbuzz import fizzbuzz

def test_fizzbuzz():
    expected = [
        '1', '2', 'Fizz', '4', 'Buzz',
        'Fizz', '7', '8', 'Fizz', 'Buzz',
        '11', 'Fizz', '13', '14', 'FizzBuzz',
        '16', '17', 'Fizz', '19', 'Buzz'
    ]
    assert fizzbuzz(20) == expected

if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__]))
