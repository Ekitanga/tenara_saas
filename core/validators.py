from pathlib import Path
from django.core.exceptions import ValidationError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}


def validate_supporting_file(value):
    if value.size > MAX_UPLOAD_BYTES:
        raise ValidationError('Files must be 5 MB or smaller.')
    if Path(value.name).suffix.lower() not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError('Only PDF, JPG, JPEG, and PNG files are allowed.')
