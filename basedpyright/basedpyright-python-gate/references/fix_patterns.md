# Fix patterns for basedpyright `recommended` mode

Read this when a rule is unfamiliar, or when you catch yourself about to reach for `Any`, `cast`, or an ignore. Each entry gives the shortcut an agent typically takes (don't) and the fix that actually makes the code correct.

Contents

1. The boundary principle (read first)
2. Unknown / Any family
3. Optional / None family
4. Signature and assignment mismatches
5. Attribute, index and call issues
6. Hygiene rules (unused, redeclared, unreachable, deprecated)
7. Class and override rules
8. Unnecessary-X rules (the checker telling you to *remove* something)
9. Stubs and imports
10. Deciding whether an ignore is legitimate

---

## 1. The boundary principle

Almost every long list of `reportUnknown*` / `reportAny` diagnostics has one or two sources: a place where data enters the program without a type. `json.loads`, `yaml.safe_load`, `request.json()`, `os.environ`, a `dict[str, Any]` that one function builds and twelve functions read, an untyped SDK.

Fix the source, not the leaves:

```python
# Before: Any leaks everywhere
def load_config(path: str):
    return json.loads(Path(path).read_text())

# After: one validating parse, typed from here on
class Config(TypedDict):
    host: str
    port: int
    retries: NotRequired[int]

def _is_config(value: object) -> TypeIs[Config]:
    match value:
        case {"host": str(), "port": int()}:
            return True
        case _:
            return False

def load_config(path: Path) -> Config:
    raw = cast("object", json.loads(path.read_text()))
    if not _is_config(raw):
        raise ValueError(f"invalid config in {path}")
    return raw
```

Note `cast("object", ...)`: widen the untyped value to `object`, never leave it `Any`. `object` forces you to narrow before use, which is the point. This is the one honest cast, because every value is an `object`, and it is required: `reportAny` flags `raw: object = json.loads(...)`, a `-> object` helper that returns it, and passing it straight into the guard. The `TypeIs` function is the single place the program vouches for the shape; nothing downstream needs a cast.

Narrow with a mapping pattern, not `isinstance(value, dict)`: that yields `dict[Unknown, Unknown]`, and every `.get()` on it is `reportUnknownMemberType`.

For nested data, a dataclass with a `from_json(cls, raw: object) -> Self` classmethod that validates field by field does the same job and is easier to extend. For large schemas, a validation library (pydantic, msgspec) is a legitimate dependency to propose — ask the user before adding it.

---

## 2. Unknown / Any family

### reportAny, reportExplicitAny

Shortcut: annotate with `Any` so the checker stops asking. That is the error, restated as a promise.

Fix: find the real type. If it comes from a boundary, see §1. If it's a function parameter that accepts "anything with `.read()`", write a `Protocol`:

```python
class Readable(Protocol):
    def read(self, n: int = ..., /) -> bytes: ...

def consume(source: Readable) -> bytes: ...
```

If it's a container of heterogeneous values, it's usually a `TypedDict` or a dataclass pretending to be a dict. If the function genuinely works for every type, it's generic:

```python
def first[T](items: Sequence[T]) -> T: ...
```

`Any` is acceptable only in a `.pyi` stub for third-party code, and even there, prefer `object`.

### reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType, reportUnknownParameterType, reportUnknownLambdaType

These are the downstream symptoms of §1. The value's type is *partially* unknown — often `list[Unknown]` or `dict[str, Unknown]` from an untyped source, an empty literal (`x = []`), or a lambda whose parameter can't be inferred.

Fixes:
- Empty collection: annotate at creation, `items: list[Order] = []`.
- Comprehension over unknown data: type the source (§1).
- Lambda: use a `def` with annotations, or annotate the variable receiving it with a `Callable[[int], str]`.
- Parameter without annotation: annotate it. If you don't know what it is, read the callers.
- Untyped third-party return: wrap the call once in a typed adapter function; the one ignore (if truly needed) goes inside the adapter, never at the call sites.

### reportMissingParameterType, reportMissingTypeArgument

Annotate the parameter; give the generic its argument (`list[str]`, not `list`). `dict` without arguments is `dict[Unknown, Unknown]` and will fan out into §2 noise.

---

## 3. Optional / None family

### reportOptionalMemberAccess, reportOptionalSubscript, reportOptionalIterable, reportOptionalCall, reportOptionalOperand

Shortcut: `assert x is not None` at every use, or `cast(Foo, x)`.

Fix depends on *why* it's optional:
- The function can't actually return `None` → fix the return type and the implementation (raise instead of returning `None`, or return a default).
- `None` is a real case → handle it once, early, at the point the value is obtained. Early return, or raise with a useful message.
- A dataclass field defaults to `None` but is always set before use → it's not optional; give it a real default, or make it required, or restructure construction so it's set in `__init__`.

`assert x is not None` is acceptable *once*, right after obtaining the value, when the invariant is documented and a failure would be a bug rather than a user error. It is not acceptable sprinkled through a function body.

### reportPossiblyUnbound

A variable assigned only on some branches. Fix: initialise before the branch, or restructure so every path assigns, or raise in the path that doesn't. Don't `# pyright: ignore` it — this is a real bug class.

---

## 4. Signature and assignment mismatches

### reportArgumentType, reportReturnType, reportAssignmentType, reportCallIssue

The checker found two sides that disagree. Shortcut: widen whichever side is easier to edit to `Any`.

Fix: decide which side is *right*. Usually the narrower one. If a function returns `str | int` and a caller needs `str`, the function has two jobs — split it, or make the return generic/overloaded, or convert at the boundary. If a parameter is declared `list[str]` but callers pass `tuple[str, ...]`, the parameter should be `Sequence[str]` (accept the broadest type you only read from; return the narrowest type you produce).

Invariance traps: `list[Dog]` is not a `list[Animal]`. Accept `Sequence[Animal]` for read-only use; if the function mutates the list, the error is legitimate and the design needs to change.

### reportIncompatibleMethodOverride, reportIncompatibleVariableOverride

The subclass signature is narrower than the base. Fix the subclass (parameters may widen, returns may narrow, never the reverse), or fix the base if the base is wrong. If the subclass genuinely needs a different signature, it isn't a subtype — compose instead of inherit.

---

## 5. Attribute, index and call issues

### reportAttributeAccessIssue

The type doesn't have that attribute. Either the type is wrong (fix the annotation upstream), the value is a union and you need to narrow, or the attribute is set dynamically (`setattr`, `__getattr__`) — in which case declare it on the class, or use a `Protocol` describing what you need.

### reportIndexIssue

Indexing something that isn't indexable, or with the wrong key type. Same approach: narrow, or fix the upstream type. For `TypedDict` keys, use `.get()` with a default for `NotRequired` keys.

### reportPrivateUsage, reportPrivateImportUsage

You're reaching for `_name` from another module, or importing a symbol from where a library re-exports it privately. Fix: import from the public location, or make the name public in the module you own. For third-party libraries, find the public export; this is rarely a legitimate ignore.

### reportUnusedCallResult (when enabled)

A call's return value is discarded. If the result doesn't matter, assign to `_`. If it does matter, that's a bug.

---

## 6. Hygiene rules

### reportUnusedVariable, reportUnusedImport, reportUnusedParameter, reportUnusedExpression

Remove it. A parameter kept for interface compatibility gets a `_` prefix. Don't ignore these; they are nearly free to fix and ignores for them are pure noise.

### reportRedeclaration

The same name is defined twice with different types or as both a function and a variable. Rename one. Loops that reuse a variable name for a different type are the common source; use two names.

### reportUnreachable

Code after a `return`/`raise`, or under a condition the checker has proven false. Remove it, or if you believe it's reachable, the type of the condition is wrong — fix that.

### reportDeprecated

Use the replacement the deprecation message names. If the deprecated API is the only way (rare), the ignore is legitimate with a reason citing the upstream issue.

### reportImplicitStringConcatenation (when enabled)

Add explicit `+`, or use a single string. Usually a missing comma in a list.

---

## 7. Class and override rules

### reportImplicitOverride

Add `@override` (from `typing`) to methods that override a base method. Mechanical; do it everywhere, never ignore it.

### reportUninitializedInstanceVariable

A declared attribute is never assigned in `__init__`. Assign it, give it a default, or if it's set in a factory, make the factory the only constructor (`__init__` takes the value).

### reportUnsafeMultipleInheritance, reportIncompatibleMethodOverride in mixins

Usually a sign that composition would be clearer. If the hierarchy is a framework requirement, type the mixin with a `Protocol` describing what it expects from `self`.

---

## 8. Unnecessary-X rules

### reportUnnecessaryIsInstance, reportUnnecessaryComparison, reportUnnecessaryCast, reportUnnecessaryContains, reportUnnecessaryTypeIgnoreComment

The checker is telling you a check or a suppression is dead. **Delete it.** These are the opposite of a problem: they prove your earlier fix worked and the belt-and-braces code is now just braces. In particular, `reportUnnecessaryTypeIgnoreComment` is how stale ignores get cleaned up; never suppress it.

If an `isinstance` is flagged unnecessary but you believe runtime data could violate the type, then the *annotation* is lying — the value should be typed `object` at the boundary and narrowed there (§1).

---

## 9. Stubs and imports

### reportMissingTypeStubs, reportMissingModuleSource, reportMissingImports

- First-party module not found: fix `include`/the package layout or the import path, don't ignore.
- Third-party without stubs: check whether a `types-*` package or an inline-typed newer version exists; propose adding it (ask the user — it's a dependency change).
- Nothing exists: write a minimal `.pyi` stub for just the surface you use, in a `typings/` directory, and point to it with… nothing — basedpyright finds `typings/` next to the pyproject by default. Prefer `object` over `Any` in stubs. This is the proper fix for vendored code too.
- Only when a stub would be unreasonable (giant dynamic SDK, you use one function): a single ignore at the single typed adapter that wraps it.

---

## 10. Deciding whether an ignore is legitimate

Ask in order; the first "no" means fix the code instead.

1. Is the code on the other side of this line something I don't own and can't reasonably stub?
2. Have I tried the proper fix from this document and found it impossible rather than inconvenient?
3. Is this the *only* place this boundary is crossed? If not, wrap it in one typed adapter first.
4. Can I state the reason in one clause that names the untyped thing?

Then write it as:

```python
result = sdk.call(arg)  # pyright: ignore[reportUnknownMemberType]  # legacy_sdk 2.x ships no types
```

Rule-scoped, reason on the same line, one clause. Report it in the final summary.
