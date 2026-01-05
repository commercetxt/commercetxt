# CommerceTXT Python Reference Parser

[![Version](https://img.shields.io/badge/version-1.0.3-blue.svg)](https://pypi.org/project/commercetxt/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-80%25%2B-green.svg)](./tests/)

**Production-ready Python parser for the CommerceTXT Protocol v1.0.1**

Robust, secure implementation with enterprise-grade security, async support, RAG tools, and AI integration.

---

## ✨ Key Features

### Core Parser
- ✅ **Full Spec Compliance** - CommerceTXT Protocol v1.0.1 (Tier 1, 2, 3 directives)
- ✅ **UTF-16/32 Support** - Auto-detect Excel exports and international encodings
- ✅ **Fractal Inheritance** - Multi-file resolution with circular dependency detection
- ✅ **Indent Auto-Detection** - Handles 2-space, 4-space, mixed indentation
- ✅ **BOM Handling** - UTF-8/UTF-16/UTF-32 Byte Order Mark detection
- ✅ **Source Mapping** - Track line numbers for debugging

### Security & Performance
- 🔒 **SSRF Protection** - Blocks private IPs, localhost, exotic IP notations
- 🔒 **DoS Mitigation** - File size (10MB), nesting depth (100), rate limits
- ⚡ **LRU Caching** - High-performance caching for repeated parses
- ⚡ **Async Support** - Concurrent bulk parsing via `AsyncCommerceTXTParser`
- 📊 **Performance Metrics** - Real-time timing and memory tracking

### AI & RAG Tools
- 🤖 **AI Bridge** - Low-token prompts (~120 tokens vs 8,500+ HTML)
- 🏥 **Health Checker** - AI readiness scoring (0-100)
- 🌐 **Schema.org Bridge** - JSON-LD conversion with full mappings
- 🔧 **Semantic Normalizer** - Standardize attributes across catalogs
- 📦 **RAG Pipeline** - Vector database integration
- ⚡ **Async RAG** - Stream-based processing

### Vector Database Support
- Pinecone, Qdrant, Redis, FAISS, In-Memory

### Validation & Testing
- ✅ **Tiered Validation** - Tier 1/2/3 compliance checks
- ✅ **80%+ Coverage** - Comprehensive test suite
- ✅ **Property-Based Tests** - Hypothesis for edge cases
- ✅ **Fuzz Testing** - Random input stress testing
- ✅ **Security Audits** - SSRF/DoS prevention

---

## 🚀 Installation

### Basic Install
```bash
pip install commercetxt
```

### With Optional Features
```bash
pip install commercetxt[cli]      # Colored CLI output
pip install commercetxt[async]    # Async file support
pip install commercetxt[rag]      # RAG tools (local bundle)
pip install commercetxt[rag-all]  # All RAG drivers
pip install commercetxt[dev]      # Development tools
```

---

## 📖 Usage Examples

### Basic Parsing
```python
from commercetxt import parse_file

# Parse commerce.txt file
result = parse_file('commerce.txt')

# Access directives
identity = result.directives.get('IDENTITY', {})
product = result.directives.get('PRODUCT', {})
offer = result.directives.get('OFFER', {})

print(f"Store: {identity.get('Name')}")
print(f"Product: {product.get('Name')}")
print(f"Price: ${offer.get('Price')}")

# Check for issues
if result.errors:
    print(f"Errors: {result.errors}")
```

### With Validation
```python
from commercetxt import parse_file, CommerceTXTValidator

result = parse_file('commerce.txt')

# Validate
validator = CommerceTXTValidator(strict=False)
validated = validator.validate(result)

print(f"Errors: {len(validated.errors)}")
print(f"Warnings: {len(validated.warnings)}")
```

### AI Bridge (Low-Token Prompts)
```python
from commercetxt import parse_file
from commercetxt.bridge import CommerceAIBridge

result = parse_file('product.txt')
bridge = CommerceAIBridge(result)

# Generate ~120 token prompt
prompt = bridge.generate_low_token_prompt()
print(prompt)

# Get AI readiness score
score = bridge.calculate_readiness_score()
print(f"Score: {score}/100")
```

### Async Bulk Processing
```python
import asyncio
from commercetxt.async_parser import AsyncCommerceTXTParser
from pathlib import Path

async def process_catalog():
    parser = AsyncCommerceTXTParser()
    
    # Read file contents
    files = ['p1.txt', 'p2.txt', 'p3.txt']
    contents = [Path(f).read_text() for f in files]
    
    # Parse concurrently
    results = await parser.parse_many(contents)
    
    for result in results:
        product = result.directives.get('PRODUCT', {})
        print(f"Processed: {product.get('Name')}")

asyncio.run(process_catalog())
```

### Caching
```python
from commercetxt.cache import parse_cached

# First call - parses
result1 = parse_cached(content)

# Second call - from cache
result2 = parse_cached(content)
```

### Fractal Inheritance
```python
from commercetxt.resolver import CommerceTXTResolver

resolver = CommerceTXTResolver()
# Resolves @INHERIT and merges
merged = resolver.resolve('https://example.com/product.txt')
```

---

## 🤖 RAG Tools

### AI Health Check
```python
from commercetxt.rag.tools import AIHealthChecker

checker = AIHealthChecker()
health = checker.check(result)

print(f"Score: {health.score}/100")
print(f"Grade: {health.grade}")
```

### Schema.org Export
```python
from commercetxt.rag.tools import SchemaBridge

bridge = SchemaBridge()
json_ld = bridge.to_json_ld(result)
print(json_ld)
```

### Semantic Normalization
```python
from commercetxt.rag.tools import SemanticNormalizer

normalizer = SemanticNormalizer()
normalized = normalizer.normalize({
    'color': 'midnight black',
    'capacity': '128GB'
})
# Output: {'color': 'black', 'storage': '128'}
```

### RAG Pipeline
```python
from commercetxt.rag import RAGGenerator
from commercetxt import parse_file

result = parse_file('commerce.txt')

generator = RAGGenerator()
shards = generator.generate(result)

for shard in shards:
    print(f"Text: {shard.text[:50]}...")
    print(f"Tags: {shard.semantic_tags}")
```

---

## 🖥️ CLI Commands

### Basic
```bash
commercetxt commerce.txt               # Parse and validate
commercetxt commerce.txt --json        # JSON output
commercetxt commerce.txt --strict      # Warnings as errors
```

### Validation
```bash
commercetxt commerce.txt --validate    # Full validation report
commercetxt product.txt --health       # AI health check
commercetxt commerce.txt --metrics     # Performance metrics
```

### AI Tools
```bash
commercetxt product.txt --prompt       # Low-token LLM prompt
commercetxt commerce.txt --schema      # Schema.org JSON-LD
```

### Product Tools
```bash
commercetxt p1.txt p2.txt --compare    # Compare products
commercetxt product.txt --normalize    # Normalize attributes
```

### Advanced
```bash
commercetxt file.txt --log-level DEBUG
commercetxt file.txt --validate --metrics --json
```

---

## 🏗️ Architecture

```
commercetxt/
├── parser.py         # Core parsing engine
├── async_parser.py   # Async concurrent parser
├── validator.py      # Validation facade
├── validators/       # Tier validators
├── bridge.py         # AI prompt generator
├── resolver.py       # Fractal inheritance
├── cache.py          # LRU caching
├── security.py       # SSRF/DoS protection
├── cli.py            # CLI interface
└── rag/              # RAG tools
    ├── pipeline.py   # RAG pipeline
    ├── core/         # Core logic
    ├── drivers/      # Vector DB drivers
    ├── tools/        # Utilities
    └── monitoring/   # Health checks
```

### Security Limits
- **MAX_FILE_SIZE:** 10 MB
- **MAX_SECTIONS:** 1,000
- **MAX_LINE_LENGTH:** 100 KB
- **MAX_NESTING_DEPTH:** 100

**Blocked Networks:**
- Localhost (127.0.0.0/8)
- Private IPs (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Link-local (169.254.0.0/16)

---

## 🧪 Testing

### Run Tests
```bash
pytest tests/                          # All tests
pytest --cov=commercetxt               # With coverage
pytest tests/test_parser.py -v        # Specific suite
```

### Test Strategy
- Unit Tests (150+ vectors)
- Integration Tests
- Property-Based (Hypothesis)
- Fuzz Tests
- Security Tests
- Performance Tests

**Coverage:** 80%+ (verified 82%)

---

## 🔧 Configuration

### Environment Variables
```bash
export COMMERCETXT_CACHE_SIZE=1000
export COMMERCETXT_LOG_LEVEL=INFO
```

### Programmatic
```python
from commercetxt import CommerceTXTParser

parser = CommerceTXTParser(
    strict=True,
    auto_detect_indent=True,
    indent_width=4
)
```

---

## 📚 Examples

See [examples directory](../../examples/):
- Basic product catalog
- Multi-language stores
- Category hierarchies
- Google Store example

---

## 🤝 Contributing

- **Repository:** https://github.com/commercetxt/commercetxt
- **Issues:** https://github.com/commercetxt/commercetxt/issues
- **Discussions:** https://github.com/commercetxt/commercetxt/discussions

---

## 📄 License

MIT License - see [LICENSE](../LICENSE)

---

## 🔗 Links

- **Protocol Spec v1.0.1:** [spec/README.md](../../spec/README.md)
- **PyPI:** https://pypi.org/project/commercetxt/
- **Website:** https://commercetxt.org
- **Changelog:** https://github.com/commercetxt/commercetxt/releases

---

**Parser v1.0.3 | Protocol v1.0.1 | Built for the Agentic Web**

