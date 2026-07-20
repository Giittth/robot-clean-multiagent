import request from "@/utils/request"

export function getApiKeyStatus() {
  return request.get("/models/keys/status")
}

export function saveApiKeys(keys) {
  return request.post("/models/keys", keys)
}
