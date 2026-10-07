import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getQuote } from '../api/quoteApi';
import QuoteSetupStep from '../components/quotes/QuoteSetupStep';
import QuoteRequirementsStep from '../components/quotes/QuoteRequirementsStep';
import QuoteStudiosStep from '../components/quotes/QuoteStudiosStep';
import QuotePreviewStep from '../components/quotes/QuotePreviewStep';
import PageHeader from '../components/common/PageHeader';
import '../styles/quotes.css';
import '../styles/wizard.css';

export default function QuoteWizardPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(!!id);
  const [draftQuote, setDraftQuote] = useState({
    client_name: '',
    attention: '',
    description: '',
    region_id: '',
    solution_id: '',
    requirement_data: {
      number_of_studios: 1,
      number_of_designers: 0,
      news_production: false,
      journalists: null,
      mos_redundancy: false,
      nle_plugin: false,
      nle_seats: null,
      nrcs_graphics_preview: false,
      sdi_production_ingest: false,
      ingest_channels: 0,
      production_playout: false,
      mam: false,
      three_years_support: false
    },
    studios: []
  });

  // Load existing quote or persist state to localStorage
  useEffect(() => {
    if (id) {
      async function loadExistingQuote() {
        try {
          const data = await getQuote(id);
          if (data.status !== 'draft') {
            navigate(`/quotes/${id}`);
            return;
          }
          setDraftQuote({
            id: data.id,
            version: data.version,
            client_name: data.client_name || '',
            attention: data.attention || '',
            description: data.description || '',
            region_id: data.region_id || '',
            solution_id: data.solution_id || '',
            requirement_data: data.requirement_data || {},
            studios: data.requirement_data?.studios || []
          });
        } catch (e) {
          console.error('Failed to load quote draft:', e);
          navigate('/quotes');
        } finally {
          setLoading(false);
        }
      }
      loadExistingQuote();
    } else {
      const savedDraft = localStorage.getItem('quote_wizard_backup');
      if (savedDraft) {
        try {
          const parsed = JSON.parse(savedDraft);
          if (parsed && typeof parsed === 'object') {
            setDraftQuote(prev => ({ ...prev, ...parsed }));
          }
        } catch (e) {
          console.error('Failed to parse saved quote draft:', e);
        }
      }
      setLoading(false);
    }
  }, [id, navigate]);

  useEffect(() => {
    // Save minimal draft state on change
    localStorage.setItem('quote_wizard_backup', JSON.stringify(draftQuote));
  }, [draftQuote]);

  const updateDraft = (updates) => {
    setDraftQuote((prev) => ({ ...prev, ...updates }));
  };

  const handleNext = () => {
    setCurrentStep((prev) => prev + 1);
  };

  const handleBack = () => {
    if (currentStep === 1) {
      navigate('/quotes');
    } else {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return (
          <QuoteSetupStep
            draftQuote={draftQuote}
            updateDraft={updateDraft}
            onNext={handleNext}
          />
        );
      case 2:
        return (
          <QuoteRequirementsStep
            draftQuote={draftQuote}
            updateDraft={updateDraft}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 3:
        return (
          <QuoteStudiosStep
            draftQuote={draftQuote}
            updateDraft={updateDraft}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 4:
        return (
          <QuotePreviewStep
            draftQuote={draftQuote}
            onBack={handleBack}
          />
        );
      default:
        return <div>Unknown Step</div>;
    }
  };

  const steps = [
    { number: 1, label: 'Setup' },
    { number: 2, label: 'Requirements' },
    { number: 3, label: 'Studios' },
    { number: 4, label: 'Preview' }
  ];

  if (loading) {
    return (
      <div className="quote-wizard-container p-4 text-center">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
        <p className="mt-3">Loading quote data...</p>
      </div>
    );
  }

  return (
    <div className="quote-wizard-container">
      <PageHeader
        title={id ? `Edit Quote: ${draftQuote.client_name}` : "Create New Quote"}
        subtitle="Step-by-step presales quotation workflow."
      />

      <div className="wizard-progress-bar">
        {steps.map((step) => (
          <div
            key={step.number}
            className={`wizard-step ${currentStep === step.number ? 'active' : ''} ${currentStep > step.number ? 'completed' : ''}`}
          >
            <div className="step-circle">{step.number}</div>
            <div className="step-label">{step.label}</div>
          </div>
        ))}
      </div>

      <div className="wizard-content">
        {renderStep()}
      </div>
    </div>
  );
}
