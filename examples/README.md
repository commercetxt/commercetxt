# CommerceTXT Examples

This directory contains real-world examples of CommerceTXT implementations, demonstrating various use cases and features of the protocol.

---

## 📁 Available Examples

### 1. Google Store (`google-store/`)
**Status:** Reference implementation  
**Products:** Pixel phones (sample catalog)  
**Features demonstrated:**
- Basic product structure
- Multi-locale support (English + German)
- Category organization
- Variant handling (colors, storage)

**View:** [Google Store Example](./google-store/)

---

### 2. IKEA US Dataset (`ikea-us/`) ⭐ **Production-Scale Example**
**Status:** ✅ Fully validated  
**Products:** 30,511 furniture and home goods  
**In this repo:** Sample (16 categories) for demonstration
**Full dataset:** [Hugging Face](https://huggingface.co/datasets/tsazan/ikea-us-commercetxt) (54 MB)

**Features demonstrated:**
- Large-scale dataset conversion (632 categories)
- Token efficiency analysis (24% savings, 3.6M tokens)
- Category-based organization
- Full product catalog with navigation structure

**View:** [IKEA US Example](./ikea-us/)

---

## 🎯 Use Cases

| Example | Best For | Complexity | Data Source |
|---------|----------|------------|-------------|
| Google Store | Learning the protocol | Beginner | Manual creation |
| IKEA US | Production implementation | Advanced | Real scraped data |

---

## 📊 Dataset Statistics

| Example | This Repo | Full Dataset | Products | Token Efficiency |
|---------|-----------|--------------|----------|------------------|
| Google Store | ~10 files (<50 KB) | N/A | 4-5 | Reference only |
| IKEA US | Sample (16 categories) | [HF](https://huggingface.co/datasets/tsazan/ikea-us-commercetxt) (54 MB) | 30,511 | 24% vs JSON |

---


## 🚀 Adding Your Own Example

Contributions welcome! To add a new example:

1. Create a new directory: `examples/your-store/`
2. Include:
   - `commerce.txt` (root file)
   - `products/` directory (if applicable)
   - `README.md` (documentation)
3. Submit a pull request

**Requirements:**
- Follow [CommerceTXT spec v1.0](../spec/README.md)
- Include proper attribution if using third-party data
- Add legal disclaimers for scraped/unofficial data

---

## 📚 Resources

- [CommerceTXT Specification](../spec/README.md)
- [Python Parser Documentation](../parsers/python/README.md)
- [Templates](../templates/)

---

## ⚖️ Legal Notes

- **Google Store Example:** Fictional data for demonstration purposes
- **IKEA US Example:** Research dataset from scraped public data (July 2025)
  - ⚠️ Not affiliated with IKEA
  - ⚠️ Static data - do not use for real shopping
  - See [`ikea-us/README.md`](./ikea-us/README.md) for full disclaimer

---

## 📬 Questions?

Open an issue on GitHub or visit [commercetxt.org](https://commercetxt.org).

