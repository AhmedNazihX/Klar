"""Every document template by id, as a draft's `template` and `interview_answers.template` name
it: the short deployer documents (P8a), the provider document skeletons (P8b) and the vendor
letters (P28). The automatic checks look a draft's template up here."""

from collections.abc import Mapping
from types import MappingProxyType

from aiact.drafting.skeletons import SKELETON_TEMPLATES
from aiact.drafting.templates import DEPLOYER_TEMPLATES, DocumentTemplate
from aiact.drafting.vendor_letters.templates import VENDOR_LETTER_TEMPLATES

TEMPLATES: Mapping[str, DocumentTemplate] = MappingProxyType(
    {
        template.id: template
        for template in (*DEPLOYER_TEMPLATES, *SKELETON_TEMPLATES, *VENDOR_LETTER_TEMPLATES)
    }
)
