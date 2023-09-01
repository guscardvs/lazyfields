## Lazy

`lazyfields` has utilities to allow for lazily defined attributes so that you can avoid some patterns like the one below or avoid calculating a property twice.

```python
class MyClass:
  def __init__(self):
    self._val = None

  def get_val(self):
    if val is None:
      self._do_something()
    return self._val
```

### lazyfield

The `lazyfields.lazyfield` descriptor streamlines the process of implementing lazy attributes. Here's how you can use it:

```python
from lazyfields import lazyfield


class MyClass:
  @lazyfield
  def expensive_value(self):
    return do_expensive_operation()

instance = MyClass()
instance.expensive_value # Does the expensive operation, saves the result and returns the value
instance.expensive_value # Returns directly the cached value

del instance.expensive_value # Cleans the cache

instance.expensive_value # redo the expensive operation

instance.expensive_value = "Other" # Overwrites the cached value with the value assigned
```

> `lazyfield` saves the value directly in the class as a hidden attribute so you don't have to worry about garbage collection or weakrefs
    

### asynclazyfield

The lazyfields.asynclazyfield descriptor tackles the same issue as lazyfield, but while preserving the asynchronous API

```python
from lazyfields import asynclazyfield

class MyClass:

  @asynclazyfield
  async def expensive_value(self):
    return await do_expensive_operation()

instance = MyClass()
await instance.expensive_value() # you still call it as a function, but it will do the same thing, call the function, store the result and return the value
await instance.expensive_value() # now it only returns the value

dellazy(instance, "expensive_value") # clear the stored value
await instance.expensive_value() # here the calculation is done again
setlazy(instance, "expensive_value", "Other") # overwrite the stored value with "Other"
```


### Helpers

`lazyfields` provides helpers to work with frozen classes or when using the asynclazyfield and need to set or reset the field manually

* `setlazy(instance: Any, attribute: str, value: Any, bypass_setattr: bool = False)` setlazy allows you to directly change the hidden attribute behind any lazy field, and the bypass_setattr parameter will instead of using the `setattr` function, use `object.__setattr__`.
* `dellazy(instance: Any, attribute: str, bypass_delattr: bool = False)` dellazy allows you to clear the value stored in the hidden attribute to allow for recalculation. Similar to setlazy the bypass_delattr parameter will use `object.__delattr__` instead of `delattr`
* `force_set(instance: Any, attribute: str, value: Any)` force_set is just a shortcut for setlazy(..., bypass_setattr=True)
* `force_del(instance: Any, attribute: str)` force_del is just a shortcut for dellazy(..., bypass_delattr=True)
* `is_initialized(instance: Any, attribute: str)`  Returns whether the lazyfield has stored a value yet, without triggering the routine inadvertently.
  
