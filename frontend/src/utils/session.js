export function getSessionId() {
  let id = localStorage.getItem("session_id")

  if (!id) {
    id = Math.random().toString(36).substring(2)
    localStorage.setItem("session_id", id)
  }

  return id
}