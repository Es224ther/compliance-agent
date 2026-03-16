"""Demo entry point: python -m sanitizer"""

from app.sanitizer.anonymizer import PIIAnonymizer
from app.sanitizer.engine import SanitizerEngine

sample_text = (
    "张三的手机是13812345678，身份证号是11010519491231002X，"
    "邮箱是zhangsan@example.com。"
)
anonymizer = PIIAnonymizer(engine=SanitizerEngine())
masked_text, pii_map = anonymizer.anonymize(text=sample_text, language="zh")

print(masked_text)
print(pii_map)
