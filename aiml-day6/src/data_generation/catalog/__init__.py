"""Single source of truth for every fact that appears in the corpus."""

from data_generation.catalog.hr_policies import COMPANY, GRADES, POLICIES
from data_generation.catalog.products import BRANDS, PHONES, TVS, siblings

__all__ = ["BRANDS", "COMPANY", "GRADES", "PHONES", "POLICIES", "TVS", "siblings"]
