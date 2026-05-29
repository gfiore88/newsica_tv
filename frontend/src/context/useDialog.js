import { useContext } from 'react'
import { DialogContext } from './dialog-context'

export const useDialog = () => useContext(DialogContext)
