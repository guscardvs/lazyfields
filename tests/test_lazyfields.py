from dataclasses import FrozenInstanceError, dataclass
from typing import Any, Callable, Coroutine, Generic, TypeVar
from unittest.mock import Mock

import pytest

from lazyfields import asynclater, later
from lazyfields._lazyfields import (
    getname,
    lazyfield,
    make_lazy_descriptor,
)

T = TypeVar("T")


class Fake(Generic[T]):
    def __init__(self, slow_func: Callable[[], T]) -> None:
        self._slow_func = slow_func

    @later
    def test(self) -> T:
        return self._slow_func()


@dataclass(init=False, frozen=True)
class FrozenFake(Fake[T]):
    def __init__(self, slow_func: Callable[[], T]) -> None:
        object.__setattr__(self, "_slow_func", slow_func)


class AsyncFake(Generic[T]):
    def __init__(self, slow_func: Callable[[], Coroutine[Any, Any, T]]) -> None:
        self._slow_func = slow_func

    @asynclater
    async def test(self) -> T:
        return await self._slow_func()


@dataclass(init=False, frozen=True)
class AsyncFrozenFake(AsyncFake[T]):
    def __init__(self, slow_func: Callable[[], T]) -> None:
        object.__setattr__(self, "_slow_func", slow_func)


def test_lazy_field_return_value_correctly():
    run_count = 0

    def slow_func():
        nonlocal run_count
        run_count += 1
        return "hello"

    fake = Fake(slow_func)
    assert fake.test == "hello"
    assert run_count == 1


def test_lazy_field_updates_value_on_set():
    mock = Mock()
    fake = Fake(mock)
    fake.test = "world"

    assert fake.test == "world"
    assert not mock.called


def test_lazy_field_resets_value_on_set():
    mock = Mock()
    mock.return_value = "hello"
    fake = Fake(mock)
    fake.test = "world"

    del fake.test

    assert fake.test == "hello"
    assert mock.called_once()


def test_lazy_field_respects_frozen_in_class():
    mock = Mock()
    mock.return_value = "hello"
    fake = FrozenFake(mock)

    assert fake.test == "hello"
    with pytest.raises(FrozenInstanceError):
        fake.test = "world"
    with pytest.raises(FrozenInstanceError):
        del fake.test


### Async


@dataclass
class MockFuture:
    return_value: str = ""
    awaitable: int = 0

    async def __call__(self):
        self.awaitable += 1
        return self.return_value


async def test_async_lazy_field_return_value_correctly():
    future = MockFuture(return_value="hello")

    fake = AsyncFake(future)
    assert await fake.test() == "hello"
    assert future.awaitable == 1


async def test_async_lazy_field_updates_value_on_set():
    mock = MockFuture()
    fake = AsyncFake(mock)
    fake.test = "world"

    assert await fake.test() == "world"
    assert not mock.awaitable


async def test_async_lazy_field_resets_value_on_set():
    mock = MockFuture(return_value="hello")

    fake = AsyncFake(mock)
    fake.test = "world"

    del fake.test

    assert await fake.test() == "hello"
    assert mock.awaitable == 1


async def test_async_lazy_field_respects_frozen_in_class():
    mock = MockFuture(return_value="hello")
    fake = AsyncFrozenFake(mock)

    assert await fake.test() == "hello"
    with pytest.raises(FrozenInstanceError):
        fake.test = "world"
    with pytest.raises(FrozenInstanceError):
        del fake.test


def test_make_lazydescriptor():
    @make_lazy_descriptor
    def generic_func(_):
        return object()

    class TestA:
        field = generic_func()

    class TestB:
        another = generic_func()

    # Ensure each descriptor has its own instance
    # and the public_name is properly provided
    assert TestA.field is not TestB.another
    assert TestA.field.public_name == "field"
    assert TestB.another.public_name == "another"

    # Ensure original lazyfield behavior is kept
    original = None
    test_a = TestA()
    for _ in range(3):
        if original is None:
            original = test_a.field
        else:
            assert original is test_a.field

    # Ensure each instance has a different cache management
    pool_size = 10
    instance_pool = [TestB() for _ in range(pool_size)]
    field_set = {item.another for item in instance_pool}
    assert len(field_set) == pool_size

    # Ensure after all executions in TestB, no change was made to test_a.field
    assert test_a.field is original


def test_lazy_descriptor_no_slots():
    class NoSlots:
        @lazyfield
        def field(self):
            return None

    instance = NoSlots()
    instance.field = "value"
    assert instance.field == "value"


def test_lazy_descriptor_with_slots():
    class WithSlots:
        __slots__ = (getname("field"),)

        @lazyfield
        def field(self):
            return None

    instance = WithSlots()
    instance.field = "value"
    assert instance.field == "value"
