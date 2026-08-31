# Add to OrgAdminResetPasswordRequest:
    password: str | None = Field(
        default=None,
        description="Figma Password Strength field alias for new_password",
        examples=["StrongPassword123!"],
    )

    @model_validator(mode="after")
    def map_password_alias(self) -> Self:
        if not (self.new_password or "").strip() and self.password is not None:
            object.__setattr__(self, "new_password", self.password)
        return self