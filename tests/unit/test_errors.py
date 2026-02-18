import pytest

from src.errors import PermanentError, QualityError, TransientError


class TestTransientError:
    def test_is_exception_subclass(self):
        assert issubclass(TransientError, Exception)

    def test_message_preserved(self):
        err = TransientError("rate limit exceeded")
        assert err.message == "rate limit exceeded"

    def test_str_repr(self):
        err = TransientError("timeout")
        assert str(err) == "TransientError: timeout"

    def test_raise_and_catch(self):
        with pytest.raises(TransientError, match="network failure"):
            raise TransientError("network failure")


class TestPermanentError:
    def test_is_exception_subclass(self):
        assert issubclass(PermanentError, Exception)

    def test_message_preserved(self):
        err = PermanentError("invalid config")
        assert err.message == "invalid config"

    def test_str_repr(self):
        err = PermanentError("repo not found")
        assert str(err) == "PermanentError: repo not found"

    def test_raise_and_catch(self):
        with pytest.raises(PermanentError, match="validation failed"):
            raise PermanentError("validation failed")


class TestQualityError:
    def test_is_exception_subclass(self):
        assert issubclass(QualityError, Exception)

    def test_message_preserved(self):
        err = QualityError("score 3.2 below floor 5.0")
        assert err.message == "score 3.2 below floor 5.0"

    def test_str_repr(self):
        err = QualityError("accuracy below threshold")
        assert str(err) == "QualityError: accuracy below threshold"

    def test_raise_and_catch(self):
        with pytest.raises(QualityError, match="below minimum"):
            raise QualityError("below minimum score floor")
