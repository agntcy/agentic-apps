
class AuthError(Exception):
  """Custom exception for Agntcy Identity authentication or authorization errors."""
  def __init__(self, message: str):
    super().__init__(message)