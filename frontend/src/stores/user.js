import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const user_id = ref(null)
  const isLoggedIn = ref(false)
  const username = ref('')

  function setUser(id, name) {
    user_id.value = id
    username.value = name
    isLoggedIn.value = true
    localStorage.setItem('user_id', id)
    localStorage.setItem('username', name)
  }

  function logout() {
    user_id.value = null
    username.value = ''
    isLoggedIn.value = false
    localStorage.removeItem('user_id')
    localStorage.removeItem('username')
  }

  function initFromStorage() {
    const storedId = localStorage.getItem('user_id')
    const storedName = localStorage.getItem('username')
    if (storedId && storedName) {
      user_id.value = parseInt(storedId)
      username.value = storedName
      isLoggedIn.value = true
    }
  }

  function setGuest() {
    user_id.value = 0
    username.value = '游客'
    isLoggedIn.value = true
  }

  return {
    user_id,
    isLoggedIn,
    username,
    setUser,
    logout,
    initFromStorage,
    setGuest
  }
})