"""error contains error classes for multifox."""


import click


class BrokenProfileException(click.ClickException):
    """BrokenProfileException marks a broken profile."""

    def __init__(self, message):
        super().__init__(message)
        self.message = f"Broken profile: {message}"

    def __str__(self):
        return self.message


class BrokenInstanceException(click.ClickException):
    """BrokenInstanceException marks a broken profile instance."""

    def __init__(self, message):
        super().__init__(message)
        self.message = f"Broken instance: {message}"

    def __str__(self):
        return self.message
