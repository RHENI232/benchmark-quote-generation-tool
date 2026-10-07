import React, { useState, useEffect } from 'react';
import { regionApi } from '../../api/regionApi';
import { solutionApi } from '../../api/solutionApi';

export default function QuoteSetupStep({ draftQuote, updateDraft, onNext }) {
  const [regions, setRegions] = useState([]);
  const [solutions, setSolutions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let isMounted = true;

    async function loadData() {
      setIsLoading(true);
      setError('');
      try {
        const [regionsData, solutionsData] = await Promise.all([
          regionApi.getRegions(),
          solutionApi.getSolutions()
        ]);

        if (isMounted) {
          setRegions(regionsData);
          setSolutions(solutionsData);
        }
      } catch (err) {
        if (isMounted) {
          setError('Failed to load setup configuration. Please try again.');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadData();
    return () => { isMounted = false; };
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    // For select fields, convert to number if possible, but keep string for empty option
    const parsedValue = (name === 'region_id' || name === 'solution_id') && value !== ''
      ? parseInt(value, 10)
      : value;

    updateDraft({ [name]: parsedValue });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onNext();
  };

  // Validation
  const isValid =
    draftQuote.client_name.trim().length > 0 &&
    draftQuote.region_id !== '' &&
    draftQuote.solution_id !== '';

  if (isLoading) {
    return (
      <div className="card">
        <div className="card-body text-center">
          <div className="spinner"></div> Loading setup configuration...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="card-body">
          <div className="error-banner">{error}</div>
        </div>
      </div>
    );
  }

  if (regions.length === 0 || solutions.length === 0) {
    return (
      <div className="card">
        <div className="card-body">
          <div className="error-banner">Missing foundational data. Ensure regions and solutions are configured in the system.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="card setup-step-card">
      <div className="card-header">
        <h2 className="card-title">Quote Setup</h2>
      </div>
      <div className="card-body">
        <form onSubmit={handleSubmit} className="setup-form">
          <div className="requirement-section">
            <h3 className="section-title">Customer Information</h3>
            <div className="form-group">
              <label className="form-label" htmlFor="client_name">
                Customer / Company Name <span className="text-danger">*</span>
              </label>
              <input
                type="text"
                id="client_name"
                name="client_name"
                className="form-input"
                value={draftQuote.client_name}
                onChange={handleInputChange}
                placeholder="e.g. Acme Broadcasting Corp"
                required
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="attention">Attention (Optional)</label>
                <input
                  type="text"
                  id="attention"
                  name="attention"
                  className="form-input"
                  value={draftQuote.attention}
                  onChange={handleInputChange}
                  placeholder="e.g. Jane Doe, Procurement Manager"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="description">Quote Description (Optional)</label>
                <input
                  type="text"
                  id="description"
                  name="description"
                  className="form-input"
                  value={draftQuote.description}
                  onChange={handleInputChange}
                  placeholder="Brief summary of the quote..."
                />
              </div>
            </div>
          </div>

          <hr className="section-divider" />

          <div className="requirement-section">
            <h3 className="section-title">Quote Configuration</h3>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="solution_id">
                  Solution <span className="text-danger">*</span>
                </label>
                <select
                  id="solution_id"
                  name="solution_id"
                  className="form-select form-select-lg"
                  value={draftQuote.solution_id}
                  onChange={handleInputChange}
                  required
                >
                  <option value="">-- Select a Solution --</option>
                  {solutions.map((solution) => (
                    <option key={solution.id} value={solution.id}>
                      {solution.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="region_id">
                  Region <span className="text-danger">*</span>
                </label>
                <select
                  id="region_id"
                  name="region_id"
                  className="form-select form-select-lg"
                  value={draftQuote.region_id}
                  onChange={handleInputChange}
                  required
                >
                  <option value="">-- Select a Region --</option>
                  {regions.map((region) => (
                    <option key={region.id} value={region.id}>
                      {region.country_name} ({region.currency_code})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="form-actions mt-6">
            <button
              type="submit"
              className="btn btn-primary btn-lg"
              disabled={!isValid}
            >
              Continue
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
