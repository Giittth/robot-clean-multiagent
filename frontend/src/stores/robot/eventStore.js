import { defineStore } from 'pinia'

export const useEventStore = defineStore('event', {
  state: () => ({
    events: []  // 每条记录 { id, timestamp, level, type, message }
  }),
  actions: {
    addEvent(event) {
      this.events.unshift(event)
      // 限制最大条数
      if (this.events.length > 500) this.events.pop()
    },
    clearEvents() {
      this.events = []
    }
  }
})