import axios_ from 'axios'

interface WindowWithGetWebAppBackendUrl extends Window {
  getWebAppBackendUrl?: (arg: string) => string
}

declare const window: WindowWithGetWebAppBackendUrl
declare const parent: WindowWithGetWebAppBackendUrl

function getBackendProdUrl() {
  const fn = window.getWebAppBackendUrl || parent.getWebAppBackendUrl
  if (typeof fn === 'function') return fn('')
  return null
}

let baseURLVite = import.meta.env.BASE_URL

const backendProdBase = getBackendProdUrl()
const localBackendPort = import.meta.env.VITE_API_PORT
const localClientPort = import.meta.env.VITE_CLIENT_PORT

if (localClientPort && localBackendPort) {
  baseURLVite = baseURLVite.replace(localClientPort, localBackendPort)
}

const baseURL = backendProdBase != null ? backendProdBase : baseURLVite

const axios = axios_.create({ baseURL })

export default axios
