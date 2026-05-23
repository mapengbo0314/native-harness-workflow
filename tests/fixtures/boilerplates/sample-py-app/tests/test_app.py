from app import hello

def test_hello():
    assert hello("Alice") == "Hello, Alice!"
    assert hello("Bob") == "Hello, Bob!"
