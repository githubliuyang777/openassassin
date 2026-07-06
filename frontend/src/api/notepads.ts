import { api } from './client'

export interface Notepad {
  id: number
  title: string
  content: string
  created_at: string
  updated_at: string
}

export interface NotepadCreate {
  title: string
  content?: string
}

export interface NotepadList {
  items: Notepad[]
  total: number
  page: number
  page_size: number
}

export function fetchNotepads(page = 1, pageSize = 20, search = '') {
  return api.get<NotepadList>('/notepads', { params: { page, page_size: pageSize, search } })
}

export function fetchNotepad(id: number) {
  return api.get<Notepad>(`/notepads/${id}`)
}

export function createNotepad(data: NotepadCreate) {
  return api.post<Notepad>('/notepads', data)
}

export function updateNotepad(id: number, data: Partial<NotepadCreate>) {
  return api.put<Notepad>(`/notepads/${id}`, data)
}

export function deleteNotepad(id: number) {
  return api.delete(`/notepads/${id}`)
}
