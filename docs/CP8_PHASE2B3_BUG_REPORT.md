# CP8 Phase 2B.3 Preview Bug Investigation Report

## 1. Issue Description
The Quote Preview screen (Step 4) was hanging indefinitely on the loading states "Calculating quote..." and "Generating quote preview...". Clicking the "Retry Calculation" button had no effect.

## 2. Root Causes Identified
During read-only discovery, two distinct bugs were found exclusively in the frontend:
1. **Double Stringification Payload Error:** The backend FastAPI route explicitly expects a valid JSON payload. The base `fetchClient` inside `frontend/src/api/client.js` was inherently applying `JSON.stringify()` to any provided `body`. However, `frontend/src/api/quoteApi.js` was *also* calling `JSON.stringify(payload)` for `previewQuote`, `createQuote`, and `saveQuoteStatus`. This resulted in a double-stringified body, causing a `422 Unprocessable Entity` validation error from the backend.
2. **Indefinite Hang on Retry:** When the preview request failed, the component transitioned to an error state. The `QuotePreviewStep.jsx` "Retry Calculation" button simply invoked `setLoading(true)` without re-triggering the `useEffect` responsible for `fetchPreview()`. As a result, the component became permanently stuck in the loading view.

## 3. Resolution
The backend was verified to be fully functional and accurate, serving as the system's source of truth. Consequently, all fixes were strictly applied to the frontend:
- **`frontend/src/api/quoteApi.js`:** Removed the redundant `JSON.stringify()` calls from the `body` payloads of `previewQuote`, `createQuote`, and `saveQuoteStatus`.
- **`frontend/src/components/quotes/QuotePreviewStep.jsx`:** Introduced a new `retryTrigger` state variable, appended it to the dependency array of the `useEffect` hook, and modified the "Retry Calculation" button to increment this trigger. This properly restarts the fetch lifecycle upon retry.

## 4. Verification
The following checks were executed to confirm system integrity:
- `npm run build`: Completed successfully.
- `pytest backend/tests -v`: All 83 tests passed successfully.
- `git diff --check`: Validated without any trailing whitespace or formatting errors.

## 5. Constraints Maintained
- **No Backend Changes:** The backend business logic, database models, and pricing algorithms remained completely untouched.
- **No Unrelated Frontend Changes:** The UI design, navigation, and RBAC functionality were unaltered.
- **No Commits Executed:** This fix was investigated and implemented locally without triggering any git commits or repository pushes, keeping in line with the instructions.
