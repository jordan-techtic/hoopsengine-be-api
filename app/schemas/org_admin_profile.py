# Add to OrganizationProfileUpdateRequest after last_name field:
    full_name: str | None = Field(
        default=None,
        description="Organization admin display name (Figma user-name / Account Settings header)",
        examples=["Jane Doe"],
    )

# Add to OrganizationProfileResponse after last_name field:
    full_name: str | None = Field(
        default=None,
        description="Organization admin display name composed from first and last name",
        examples=["Jane Doe"],
    )
    role: str | None = Field(
        default=None,
        description="Authenticated user role label for Account Settings (e.g. Organization Admin)",
        examples=["Organization Admin"],
    )

# Update build_organization_profile_payload in app/services/org_admin_profile.py to set:
# full_name = f"{user.first_name} {user.last_name}".strip() or None
# role = user.role