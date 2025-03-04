import { configureStore } from '@reduxjs/toolkit';
import voiceReducer from './reducers/voiceReducer';
import ttsReducer from './reducers/ttsReducer';
import coursewareReducer from './reducers/coursewareReducer';

export const store = configureStore({
  reducer: {
    voice: voiceReducer,
    tts: ttsReducer,
    courseware: coursewareReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch; 