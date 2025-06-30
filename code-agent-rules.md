# Claude Code Opus: Python Development Rules - Optimized

## 🚨 CRITICAL RULES - MUST FOLLOW

1. **[PRIMARY] Code Discovery First**: ALWAYS search for existing implementations before writing ANY code
2. **[TDD] Test-Driven Development**: Red-Green-Refactor with mandatory pause points
3. **[EVOLUTION] No Backwards Compatibility**: Break things freely, comment out obsolete code

## ⚡ Quick Reference Card

### Before Writing Code

```
1. Search existing code (grep, glob, read)
2. If found → reuse/extend/refactor following TDD
3. If not found → proceed to TDD
```

### TDD Workflow

```
RED → Write failing tests → PAUSE → "Approved"? →
GREEN → Write minimal code → PAUSE → Review →
REFACTOR → Full test suite → Improve → Full test suite
```

### When Code Becomes Obsolete

```
1. Comment out (never delete)
2. Add markers: # OBSOLETE: [Date] - [Reason]
3. Notify author immediately
```

---

## 📋 Rule Hierarchy

### 🔴 CRITICAL (Mandatory - No Exceptions)

#### 1. PRIMARY RULE: Code Discovery Before Creation

-   **First Action**: Search extensively before creating
-   **Search Requirements**:
    -   Minimum 3 different search patterns
    -   Read at least 5 relevant files
    -   Check imports in related modules
    -   Review top 10 search results
-   **Tools**: `grep -r`, `glob **/*.py`, read multiple files
-   **Only Create If**: No suitable existing implementation found after meeting search requirements
-   **Preference Order**: Reuse → Extend → Refactor → Create New

#### 2. Test-Driven Development (TDD)

**Mandatory for**: All features and bug fixes

| Phase    | Actions                           | Pause Point          |
| -------- | --------------------------------- | -------------------- |
| RED      | Write failing tests               | ✋ Wait for approval |
| GREEN    | Minimal code to pass              | ✋ Wait for review   |
| REFACTOR | Improve without changing behavior | No pause             |

**Pause Acceptance**: "Approved", "Yes", "Continue", "Proceed", "LGTM", "Looks good"
**Pause Duration**: Indefinite - wait for author response

**Special Cases**:

-   Test modifications during GREEN → ✋ PAUSE for approval
-   Full test suite required before/after refactor

#### 3. No Backwards Compatibility

-   **Never**: Maintain compatibility layers
-   **Always**: Comment obsolete code with markers
-   **Format**: `# OBSOLETE: [Date] - [Reason]`
-   **Notify**: List all obsoleted sections to author

### 🟡 ESSENTIAL (Core Principles)

#### SOLID Principles - Python Style

| Principle                 | Implementation                                  |
| ------------------------- | ----------------------------------------------- |
| **S**ingle Responsibility | One purpose per function/class/module           |
| **O**pen/Closed           | Use decorators, callbacks, dependency injection |
| **L**iskov Substitution   | Subclasses fully replace base classes           |
| **I**nterface Segregation | Small, specific interfaces (Protocol/ABC)       |
| **D**ependency Inversion  | Depend on abstractions, inject dependencies     |

#### Python Standards

-   **Style**: PEP 8 (4 spaces, 79 chars, snake_case)
-   **Testing**: pytest preferred, 80%+ coverage
-   **Docs**: Google/NumPy docstrings for all public APIs
-   **Errors**: EAFP (try/except) over LBYL (if checks)
-   **Structure**: venv + standard project layout

### 🟢 IMPORTANT (Best Practices)

#### Code Quality Checklist

-   [ ] Type hints for public APIs
-   [ ] No print() - use logging
-   [ ] No hardcoded secrets
-   [ ] Meaningful names
-   [ ] Max 3 nesting levels
-   [ ] Max 5 function parameters

#### Performance Guidelines

-   Profile before optimizing
-   Use comprehensions and generators
-   Cache expensive operations
-   Consider async for I/O

---

## 🚫 Forbidden Practices

1. Global mutable state
2. eval()/exec() with user input
3. Bare except clauses
4. Deep nesting (>3 levels)
5. Mutable default arguments
6. Backwards compatibility code
7. Dead uncommented code
8. Monkey patching in production

---

## ⚖️ Conflict Resolution Matrix

| Situation                | PRIMARY RULE | TDD          | No Backwards Compat | Resolution                                                |
| ------------------------ | ------------ | ------------ | ------------------- | --------------------------------------------------------- |
| Found code without tests | Reuse        | Needs tests  | Can break           | Write tests for existing code FIRST, then TDD for changes |
| Found deprecated code    | Consider it  | Test new     | Must comment        | Comment old, write new with TDD                           |
| Found partial match      | Extend       | Test changes | Can modify          | Extend with tests, comment obsolete parts                 |
| Multiple implementations | Pick best    | Test choice  | Clean up others     | Use best, comment others as OBSOLETE                      |

## 📊 Decision Trees

### When to Write New Code?

```
Need functionality?
├─ YES → Search existing code
│   ├─ Found similar? → Reuse/Extend/Refactor
│   └─ Nothing found? → Proceed to TDD
└─ NO → Don't write code
```

### TDD Exception Cases

```
Task type?
├─ Feature/Bug fix → TDD Required
├─ Prototype → Mark as prototype, skip TDD
├─ Pure refactor → Skip TDD if tests exist
└─ Docs/Config → Skip TDD
```

### Handling Obsolete Code

```
New code makes old obsolete?
├─ YES → Comment out old code
│   ├─ Add OBSOLETE markers
│   ├─ Reference new implementation
│   └─ Notify author with list
└─ NO → Keep both implementations
```

---

## 🎯 Execution Workflow

1. **Receive Task**
2. **Search Existing Code** (PRIMARY RULE)
3. **Plan with TDD** if creating new
4. **RED Phase** → PAUSE
5. **GREEN Phase** → PAUSE
6. **REFACTOR Phase**
7. **Validate** (lint, format, full tests)
8. **Document Changes**

---

## 💡 Quick Reminders

-   **Search First**: Exhaust all search options before creating
-   **Test First**: Write tests before implementation
-   **Break Things**: No compatibility concerns
-   **Clean Code**: Readability > Cleverness
-   **Ask When Stuck**: Use pause points effectively

---

## 📐 Project Structure Template

```
project/
├── src/
│   └── package/
├── tests/
├── docs/
├── requirements.txt
└── .gitignore
```

---

## 🛠️ Error Scenarios

### Test Issues

| Problem                | Solution                                                |
| ---------------------- | ------------------------------------------------------- |
| Flaky tests            | Re-run 3x, if still flaky → notify author with evidence |
| Test suite too slow    | Notify author: "Test suite optimization needed"         |
| Missing test runner    | Ask author for test command                             |
| Import errors in tests | Check virtual environment, dependencies                 |

### Code Discovery Issues

| Problem                | Solution                                          |
| ---------------------- | ------------------------------------------------- |
| Too many results (50+) | Filter by: recency, imports, directory proximity  |
| Unclear if match fits  | Read implementation, check usage examples         |
| External dependency    | Check if already imported, avoid new dependencies |

### Pause Point Issues

| Problem             | Solution                                               |
| ------------------- | ------------------------------------------------------ |
| Author unresponsive | Wait indefinitely, send reminder after reasonable time |
| Unclear response    | Ask for clarification: "Should I proceed? (Yes/No)"    |
| Partial approval    | List concerns, ask for specific approval on each       |

## 🔧 Tool Commands

### Cross-Platform Commands

| Task       | Linux/Mac             | Windows                | Python Alternative     |
| ---------- | --------------------- | ---------------------- | ---------------------- |
| Search     | `grep -r "pattern"`   | `findstr /s "pattern"` | Use agent search tools |
| Find files | `find . -name "*.py"` | `dir /s /b *.py`       | `glob.glob("**/*.py")` |
| Test       | `pytest -v`           | `pytest -v`            | `python -m pytest`     |
| Lint       | `flake8`              | `flake8`               | `python -m flake8`     |
| Format     | `black .`             | `black .`              | `python -m black`      |

**Note**: Prefer Python alternatives when platform is uncertain
