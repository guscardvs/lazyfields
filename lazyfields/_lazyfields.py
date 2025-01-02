import contextlib
import functools
import typing
from collections.abc import Callable

from typing_extensions import Self

T = typing.TypeVar("T")
SelfT = typing.TypeVar("SelfT")

_obj_setattr = object.__setattr__
_obj_delattr = object.__delattr__
_obj_getattr = object.__getattribute__


class InvalidField(KeyError):
    """Raised when an unexpected result is encountered during a field lookup on a mapping."""


class lazy:
    """Represents a lazy descriptor"""

    private_name: str
    public_name: str

    @staticmethod
    def _make_private(public_name: str) -> str:
        """
        Generates the name of the private attribute based on the provided public name.

        Args:
            public_name (str): The public name of the lazy-loaded property.

        Returns:
            str: The generated private attribute name."""
        return f"_lazyfield_{public_name}"

    def __set_name__(self, owner: type[SelfT], name: str):
        """
        Sets the public and private names for the lazy field descriptor.

        Args:
            owner (type): The class that owns the descriptor.
            name (str): The name of the attribute."""
        self.public_name = name
        self.private_name = self._make_private(name)


class lazyfield(lazy, typing.Generic[SelfT, T]):
    """
    A descriptor class that can be used as a decorator for a method on a class.
    When the decorated method is accessed on an instance, it will check if the
    instance has an attribute with the same name as the method but with an
    underscore prefix. If the attribute does not exist, it will call the decorated
    method on the instance and set the result as the attribute's value.
    Subsequent accesses will return the cached value, avoiding unnecessary
    recalculation or computation.
    """

    def __init__(
        self,
        func: Callable[[SelfT], T],
        lock: typing.ContextManager = contextlib.nullcontext(),
    ) -> None:
        """
        Initializes the lazy field descriptor.

        Args:
            func (callable): The function that will be decorated.
            lock (ContextManager): A context manager that will be used to acquire a lock before accessing the attribute.
        """
        self._func = func
        self._lock = lock

    @typing.overload
    def __get__(self, instance: SelfT, owner: type[SelfT]) -> T: ...

    @typing.overload
    def __get__(self, instance: typing.Literal[None], owner: type[SelfT]) -> Self: ...

    def __get__(
        self,
        instance: typing.Optional[SelfT],
        owner: typing.Optional[type[SelfT]] = None,
    ) -> typing.Union[T, Self]:
        if not instance:
            return self
        return self._do_get(instance)

    def _do_get(self, instance: SelfT) -> T:
        with self._lock:
            try:
                val = typing.cast(
                    T,
                    _obj_getattr(
                        instance,
                        self.private_name,
                    ),
                )
            except AttributeError:
                val = self._try_set(instance)
            return val

    def _try_set(self, instance: SelfT) -> T:
        try:
            result = self._func(instance)
        except Exception as e:
            # remove exception context to create easier traceback
            raise e from None
        else:
            force_set(instance, self.public_name, result)
            return result

    def __set__(self, instance: SelfT, value: T):
        with self._lock:
            setlazy(instance, self.public_name, value)

    def __delete__(self, instance: SelfT):
        with self._lock:
            dellazy(instance, self.public_name)


class asynclazyfield(lazy, typing.Generic[SelfT, T]):
    """
    A descriptor class for asynchronously lazy-loading attributes on a class.

    When the decorated method is accessed on an instance, it will check if the
    instance has an attribute with the same name as the method but with an
    underscore prefix. If the attribute does not exist, it will call the decorated
    asynchronous method on the instance and set the result as the attribute's value.
    Subsequent accesses will return the cached value, avoiding unnecessary
    recalculation or computation.
    """

    def __init__(
        self,
        func: Callable[[SelfT], typing.Coroutine[typing.Any, typing.Any, T]],
        lock: typing.AsyncContextManager = contextlib.nullcontext(),
    ) -> None:
        """
        Initializes the asynclazyfield descriptor.

        Args:
            func (callable): The asynchronous function that will be decorated."""
        self._func = func
        self._lock = lock

    async def __call__(self, instance: SelfT) -> T:
        """
        Call the asynchronous method to load the attribute's value.

        Args:
            instance (SelfT): The instance of the class.

        Returns:
            T: The loaded value of the attribute.
        """
        async with self._lock:
            try:
                val = typing.cast(
                    T,
                    _obj_getattr(
                        instance,
                        self.private_name,
                    ),
                )
            except AttributeError:
                val = await self._try_set(instance)
            return val

    async def _try_set(self, instance: SelfT) -> T:
        """
        Attempt to set the value of the attribute using the asynchronous method.

        Args:
            instance (SelfT): The instance of the class.

        Returns:
            T: The loaded value of the attribute.

        Raises:
            Exception: If the asynchronous method raises an exception.
        """
        try:
            result = await self._func(instance)
        except Exception as e:
            raise e from None
        else:
            force_set(instance, self.public_name, result)
            return result

    @typing.overload
    def __get__(
        self, instance: SelfT, owner
    ) -> Callable[[], typing.Coroutine[typing.Any, typing.Any, T]]: ...

    @typing.overload
    def __get__(self, instance: typing.Literal[None], owner) -> Self: ...

    def __get__(
        self, instance: typing.Optional[SelfT], owner=None
    ) -> typing.Union[Callable[[], typing.Coroutine[typing.Any, typing.Any, T]], Self]:
        """
        Get the wrapped asynchronous method or the descriptor itself.

        Args:
            instance (typing.Optional[SelfT]): The instance of the class.
            owner (type[SelfT]): The class that owns the descriptor.

        Returns:
            Union[
                Callable[[], typing.Coroutine[Any, Any, T]],
                Self
            ]: The asynchronous method or the descriptor itself.
        """
        if not instance:
            return self
        return functools.partial(self.__call__, instance=instance)

    def __set__(self, instance: SelfT, value: T) -> None:
        setlazy(instance, self.public_name, value)

    def __delete__(self, instance: SelfT) -> None:
        dellazy(instance, self.public_name)


def _getlazy(instance: typing.Any, attribute: str) -> lazy:
    """
    Get the lazy descriptor associated with the specified attribute on an instance.

    Args:
        instance (Any): The instance to retrieve the descriptor from.
        attribute (str): The name of the lazy-loaded property.

    Returns:
        lazy: The lazy descriptor associated with the attribute.

    Raises:
        InvalidField: If the attribute is not a lazy descriptor.
    """
    lazyf = getattr(type(instance), attribute, None)
    if not isinstance(lazyf, lazy):
        raise InvalidField(
            f"Field {attribute} expected to be lazy but received {type(lazyf)}"
        )
    return lazyf


def setlazy(
    instance: typing.Any,
    attribute: str,
    value: typing.Any,
    bypass_setattr: bool = False,
):
    """
    Set the value of a lazy-loaded property on an instance.

    Args:
        instance (Any): The instance to set the property on.
        attribute (str): The name of the lazy-loaded property.
        value (Any): The value to set for the property.
        bypass_setattr (bool): If True, directly set the attribute using `object.__setattr__`
                               to bypass immutability issues. (default: False)

    Raises:
        InvalidField: If the attribute is not a lazy descriptor.
    """
    lazy = _getlazy(instance, attribute)
    setter = _obj_setattr if bypass_setattr else setattr
    setter(instance, lazy.private_name, value)


def force_set(instance: typing.Any, attribute: str, value: typing.Any):
    """
    Forcefully set the value of a lazy-loaded property on an instance.

    Args:
        instance (Any): The instance to set the property on.
        attribute (str): The name of the lazy-loaded property.
        value (Any): The value to set for the property.
    """
    setlazy(instance, attribute, value, bypass_setattr=True)


def dellazy(instance: typing.Any, attribute: str, bypass_delattr: bool = False):
    """
    Delete the value of a lazy-loaded property on an instance.

    Args:
        instance (Any): The instance to delete the property from.
        attribute (str): The name of the lazy-loaded property.
        bypass_delattr (bool): If True, directly delete the attribute using `object.__delattr__`
                               to bypass immutability issues. (default: False)

    Raises:
        InvalidField: If the attribute is not a lazy descriptor.
    """
    lazy = _getlazy(instance, attribute)
    deleter = _obj_delattr if bypass_delattr else delattr
    deleter(instance, lazy.private_name)


def force_del(instance: typing.Any, attribute: str):
    """
    Forcefully delete the value of a lazy-loaded property on an instance.

    Args:
        instance (Any): The instance to set the property on.
        attribute (str): The name of the lazy-loaded property.
    """
    dellazy(instance, attribute, bypass_delattr=True)


SENTINEL = object()


def is_initialized(instance: typing.Any, attribute: str) -> bool:
    lazyf = _getlazy(instance, attribute)
    return getattr(instance, lazyf.private_name, SENTINEL) is not SENTINEL


@typing.overload
def later(
    func: None = None,
    /,
    *,
    lock: typing.ContextManager = contextlib.nullcontext(),
) -> Callable[[Callable[[SelfT], T]], lazyfield[SelfT, T]]: ...


@typing.overload
def later(
    func: Callable[[SelfT], T],
    /,
    *,
    lock: typing.ContextManager = contextlib.nullcontext(),
) -> lazyfield[SelfT, T]: ...


def later(
    func: Callable[[SelfT], T] | None = None,
    /,
    *,
    lock: typing.ContextManager = contextlib.nullcontext(),
) -> lazyfield[SelfT, T] | Callable[[Callable[[SelfT], T]], lazyfield[SelfT, T]]:
    """
    A decorator that can be used to mark a method as a lazy field.

    Args:
        func (Callable[[], T] | None): The function to be decorated.
        lock_factory (Callable[[], ContextManager]): A factory function for creating a context manager.

    Returns:
        lazyfield[T] | Callable[[Callable[[], T], lazyfield[T]]: The decorated function or a decorator that can be used to decorate another function.
    """
    if func is not None:
        return lazyfield(func, lock)

    def decorator(func: Callable[[SelfT], T]) -> lazyfield[SelfT, T]:
        return lazyfield(func, lock)

    return decorator


@typing.overload
def asynclater(
    func: None = None,
    /,
    *,
    lock: typing.AsyncContextManager = contextlib.nullcontext(),
) -> Callable[
    [Callable[[SelfT], typing.Coroutine[typing.Any, typing.Any, T]]],
    asynclazyfield[SelfT, T],
]: ...


@typing.overload
def asynclater(
    func: Callable[[SelfT], typing.Coroutine[typing.Any, typing.Any, T]],
    /,
    *,
    lock: typing.AsyncContextManager = contextlib.nullcontext(),
) -> asynclazyfield[SelfT, T]: ...


def asynclater(
    func: Callable[[SelfT], typing.Coroutine[typing.Any, typing.Any, T]] | None = None,
    /,
    *,
    lock: typing.AsyncContextManager = contextlib.nullcontext(),
) -> (
    asynclazyfield[SelfT, T]
    | Callable[
        [Callable[[SelfT], typing.Coroutine[typing.Any, typing.Any, T]]],
        asynclazyfield[SelfT, T],
    ]
):
    """
    A decorator that can be used to mark a method as an async lazy field.

    Args:
        func (Callable[[], typing.Coroutine[Any, Any, T]] | None): The function to be decorated.
        lock_factory (Callable[[], AsyncContextManager]): A factory function for creating an async context manager.

    Returns:
        asynclazyfield[T] | Callable[[Callable[[], typing.Coroutine[Any, Any, T]], asynclazyfield[T]]: The decorated function or a decorator that can be used to decorate another function.
    """
    if func is not None:
        return asynclazyfield(func, lock)

    def decorator(
        func: Callable[[SelfT], typing.Coroutine[typing.Any, typing.Any, T]],
    ) -> asynclazyfield[SelfT, T]:
        return asynclazyfield(func, lock)

    return decorator


def make_lazy_descriptor(
    func: Callable[[SelfT], T],
) -> Callable[[], lazyfield[SelfT, T]]:
    """
    Creates a partial function for creating a lazy field descriptor.

    Args:
        func (Callable[[SelfT], T]): The function that will be wrapped by the lazy descriptor.

    Returns:
        Callable[[], lazyfield[SelfT, T]]: A function that when called returns a lazyfield descriptor
        wrapping the input function.
    """
    return functools.partial(lazyfield, func)


def getname(name: str):
    """
    Get the private name for a lazy field based on the input name.

    Args:
        name (str): The public name of the lazy field.

    Returns:
        str: The generated private name.
    """
    return lazy._make_private(name)


def is_slotted(anything: type):
    """
    Determines if a class or type is slotted (i.e., has a __slots__ attribute).

    A class is considered slotted if it defines the __slots__ attribute,
    which is used to limit the attributes that instances of the class can have.
    This method checks for the presence of __slots__ in the class itself or its
    base classes in the method resolution order (MRO).

    Args:
        anything (type): The class or type to check.

    Returns:
        bool: True if the class is slotted, False otherwise.

    Notes:
        - A class with an empty __slots__ tuple is not considered slotted.
        - This function may have limitations in edge cases with certain base classes
          like `typing.Generic` that define __slots__ but don't function as slotted
          classes in the typical sense.
    """
    if not hasattr(anything, "__slots__"):
        return False
    if anything.__slots__:
        return True
    # Traverse the MRO of the class (excluding the class itself)
    return not any(hasattr(base, "__slots__") for base in anything.mro()[1:])
