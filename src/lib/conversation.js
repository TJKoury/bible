import { parsePassages } from './retrieval.js';

const MAX_PRIOR_TURNS = 3;
const MAX_PRIOR_QUESTION_LENGTH = 1200;

/** Conservative, deterministic follow-up detection; no model rewriting. */
export function isFollowUp(question) {
  const text = String(question || '').trim();
  if (!text || parsePassages(text).length) return false;
  if (/^(?:new (?:question|topic)|separately|unrelated|instead|start over|switch (?:the )?topics?)\b/i.test(text)) return false;
  if (/^(?:and\b|also\b|but\b|then\b|what about\b|how about\b|tell me more\b|go on\b|continue\b|expand\b|elaborate\b)/i.test(text)) return true;
  if (/^(?:why|how so|why not|in what way|what else|any others|more details)[?.!\s]*$/i.test(text)) return true;
  if (/^(?:explain|clarify|compare|support|justify|cite|show|where|which|what|why|how|can|could|would|does|do|is|are)\b/i.test(text) &&
      /\b(?:that|this|it|those|these|they|them|their|above|previous|earlier|same)\b/i.test(text)) return true;
  return false;
}

/**
 * Reuse only the selected question's parent chain, never adjacent unrelated
 * timeline items or previous model answers. `context` is the selected passage
 * snapshot for follow-ups and the current reading for standalone questions.
 */
export function buildConversationContext(question, { history = [], selectedId = '', context = null, maxTurns = MAX_PRIOR_TURNS } = {}) {
  const currentQuestion = String(question || '').trim();
  const byId = new Map(history.filter(item => item && typeof item.id === 'string').map(item => [item.id,item]));
  const selected = byId.get(selectedId);
  const limit = Math.max(0,Math.min(MAX_PRIOR_TURNS,Number.isFinite(maxTurns) ? Math.floor(maxTurns) : MAX_PRIOR_TURNS));
  const followUp = Boolean(selected?.question && limit && isFollowUp(currentQuestion));
  const prior = [], seen = new Set();
  let item = followUp ? selected : null;
  while (item && prior.length < limit && !seen.has(item.id)) {
    seen.add(item.id);
    if (typeof item.question === 'string' && item.question.trim()) {
      prior.unshift({ id:item.id, question:item.question.trim().slice(0,MAX_PRIOR_QUESTION_LENGTH) });
    }
    item = typeof item.parentId === 'string' ? byId.get(item.parentId) : null;
  }
  const priorQuestions = prior.map(item => item.question);
  // Keep exact user wording. Question labels are confined to the model-facing
  // context and do not become retrieval keywords.
  const searchQuestion = [...priorQuestions,currentQuestion].filter(Boolean).join('\n');
  const selectionQuestion = prior.length
    ? `Previous user questions, oldest first:\n${priorQuestions.map((text,index)=>`${index+1}. ${text}`).join('\n')}\n\nCurrent follow-up question:\n${currentQuestion}`
    : currentQuestion;
  return {
    question:currentQuestion,
    searchQuestion,
    selectionQuestion,
    followUp,
    parentId:followUp ? selected.id : '',
    priorQuestionIds:prior.map(item=>item.id),
    priorQuestions,
    context:followUp ? selected.context || context : context,
  };
}
