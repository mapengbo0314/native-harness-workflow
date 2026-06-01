import express from 'express'
import cors from 'cors'
import dotenv from 'dotenv'
import path from 'path'
import { getDb } from './db'
import { reposRouter } from './routes/repos'
import { repoRouter } from './routes/repo'
import { scanRouter } from './routes/scan'

dotenv.config({ path: path.join(__dirname, '../../.env') })

const app = express()
const PORT = Number(process.env.PORT ?? 3001)

app.use(cors())
app.use(express.json())

app.use('/api/repos', reposRouter)
app.use('/api/repos', repoRouter)
app.use('/api/repos', scanRouter)

if (process.env.NODE_ENV === 'production') {
  const clientDist = path.join(__dirname, '../../../dist/client')
  app.use(express.static(clientDist))
  app.get('*', (_req, res) => res.sendFile(path.join(clientDist, 'index.html')))
}

getDb() // initialise schema on startup

app.listen(PORT, () => console.log(`bz-dashboard running on http://localhost:${PORT}`))
