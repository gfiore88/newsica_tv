import React, { createContext, useContext, useState, useCallback } from 'react';
import { AlertCircle, HelpCircle, X } from 'lucide-react';

const DialogContext = createContext();

export const useDialog = () => useContext(DialogContext);

export function DialogProvider({ children }) {
  const [dialog, setDialog] = useState(null);

  const showAlert = useCallback((message, title = 'Attenzione') => {
    return new Promise((resolve) => {
      setDialog({
        type: 'alert',
        title,
        message,
        onConfirm: () => {
          setDialog(null);
          resolve(true);
        }
      });
    });
  }, []);

  const showConfirm = useCallback((message, title = 'Conferma Azione') => {
    return new Promise((resolve) => {
      setDialog({
        type: 'confirm',
        title,
        message,
        onConfirm: () => {
          setDialog(null);
          resolve(true);
        },
        onCancel: () => {
          setDialog(null);
          resolve(false);
        }
      });
    });
  }, []);

  return (
    <DialogContext.Provider value={{ showAlert, showConfirm }}>
      {children}

      {dialog && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 shadow-2xl rounded-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="p-4 flex items-center justify-between border-b border-slate-800 bg-slate-800/50">
              <div className="flex items-center gap-3">
                {dialog.type === 'confirm' ? (
                  <HelpCircle className="text-amber-500" size={24} />
                ) : (
                  <AlertCircle className="text-sky-500" size={24} />
                )}
                <h3 className="font-bold text-slate-200">{dialog.title}</h3>
              </div>
              <button 
                onClick={dialog.type === 'confirm' ? dialog.onCancel : dialog.onConfirm}
                className="text-slate-400 hover:text-white transition"
              >
                <X size={20} />
              </button>
            </div>
            
            <div className="p-6">
              <p className="text-slate-300 whitespace-pre-wrap">{dialog.message}</p>
            </div>
            
            <div className="p-4 bg-slate-950 flex justify-end gap-3 border-t border-slate-800">
              {dialog.type === 'confirm' && (
                <button
                  onClick={dialog.onCancel}
                  className="px-4 py-2 rounded-lg text-sm font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition border border-slate-700"
                >
                  Annulla
                </button>
              )}
              <button
                onClick={dialog.onConfirm}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition shadow-lg ${
                  dialog.type === 'confirm' 
                    ? 'bg-amber-600 hover:bg-amber-500 text-white shadow-amber-600/20' 
                    : 'bg-sky-600 hover:bg-sky-500 text-white shadow-sky-600/20'
                }`}
              >
                {dialog.type === 'confirm' ? 'Conferma' : 'OK'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DialogContext.Provider>
  );
}
