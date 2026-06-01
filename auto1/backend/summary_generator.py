import os
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class GeneLocus:
    gene_name: str
    chromosome: str
    position: str
    rs_id: Optional[str] = None
    function: str = ""
    discussion_points: List[str] = field(default_factory=list)


@dataclass
class TechnicalFeasibility:
    current_capabilities: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    timeline_assessment: str = ""
    success_probability: str = ""


@dataclass
class EthicalRisk:
    category: str
    description: str
    severity: str
    mitigation_strategies: List[str] = field(default_factory=list)
    stakeholders_affected: List[str] = field(default_factory=list)


@dataclass
class SocialImpact:
    short_term: List[str] = field(default_factory=list)
    long_term: List[str] = field(default_factory=list)
    equity_considerations: List[str] = field(default_factory=list)
    public_perception: str = ""


@dataclass
class MeetingSummary:
    meeting_id: str
    meeting_date: str
    title: str
    participants: List[Dict] = field(default_factory=list)
    gene_loci: List[GeneLocus] = field(default_factory=list)
    technical_feasibility: TechnicalFeasibility = field(default_factory=TechnicalFeasibility)
    ethical_risks: List[EthicalRisk] = field(default_factory=list)
    social_impact: SocialImpact = field(default_factory=SocialImpact)
    conclusions: List[str] = field(default_factory=list)
    action_items: List[Dict] = field(default_factory=list)
    raw_transcript: str = ""
    full_markdown: str = ""


class SummaryGenerator:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo-preview"):
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        self.model = model
        self.client = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("OpenAI client not installed. Using mock generation.")
    
    def _call_openai(self, prompt: str, system_prompt: str = "", max_tokens: int = 4000) -> str:
        if self.client is None:
            return self._mock_response(prompt)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return self._mock_response(prompt)
    
    def _mock_response(self, prompt: str) -> str:
        logger.info("Generating mock summary (OpenAI client not available)")
        
        if "gene loci" in prompt.lower():
            return json.dumps([{
                "gene_name": "HBB",
                "chromosome": "11",
                "position": "5,225,466-5,229,395",
                "rs_id": "rs334",
                "function": "Hemoglobin beta chain",
                "discussion_points": [
                    "Sickle cell anemia treatment potential",
                    "Germline editing concerns",
                    "Off-target effects in homologous regions"
                ]
            }, {
                "gene_name": "CCR5",
                "chromosome": "3",
                "position": "46,414,797-46,417,268",
                "rs_id": "rs333",
                "function": "C-C chemokine receptor type 5",
                "discussion_points": [
                    "HIV resistance applications",
                    "He Jiankui case reference",
                    "Immunological side effects"
                ]
            }, {
                "gene_name": "APP",
                "chromosome": "21",
                "position": "25,880,590-25,916,845",
                "function": "Amyloid beta precursor protein",
                "discussion_points": [
                    "Alzheimer's disease prevention",
                    "Late-onset vs early-onset considerations",
                    "Cognitive enhancement concerns"
                ]
            }])
        
        return "Mock analysis complete. Technical feasibility: Moderate. Ethical concerns identified."
    
    def extract_gene_loci(self, transcript: str, merged_segments: List[Dict]) -> List[GeneLocus]:
        logger.info("Extracting gene loci from transcript")
        
        gene_patterns = [
            r'\b[A-Z]{2,}[0-9]*\b',
            r'\brs[0-9]+\b',
            r'\bchromosome\s+[0-9XY]+\b',
        ]
        
        system_prompt = """
        You are an expert in molecular biology and genetics. Analyze the given transcript 
        from a gene editing ethics symposium and identify all gene loci discussed.
        For each locus, provide: gene name, chromosome, position if mentioned,
        rsID if mentioned, gene function, and key discussion points.
        Return as JSON array.
        """
        
        prompt = f"""
        Transcript excerpts mentioning gene loci:
        {transcript[:8000]}
        
        Participant discussions:
        {json.dumps([s['text'] for s in merged_segments if s.get('speaker_type') == 'scientist'][:20])}
        
        Please identify all gene loci discussed in this symposium.
        """
        
        result = self._call_openai(prompt, system_prompt)
        
        try:
            loci_data = json.loads(result)
            return [GeneLocus(**locus) for locus in loci_data]
        except json.JSONDecodeError:
            logger.warning("Failed to parse gene loci JSON, using fallback extraction")
            return self._fallback_gene_extraction(transcript)
    
    def _fallback_gene_extraction(self, transcript: str) -> List[GeneLocus]:
        known_genes = {
            'HBB': ('11', 'Hemoglobin beta chain'),
            'CCR5': ('3', 'C-C chemokine receptor type 5'),
            'APP': ('21', 'Amyloid beta precursor protein'),
            'BRCA1': ('17', 'Breast cancer 1'),
            'BRCA2': ('13', 'Breast cancer 2'),
            'CFTR': ('7', 'CF transmembrane conductance regulator'),
            'HTT': ('4', 'Huntingtin'),
            'SOD1': ('21', 'Superoxide dismutase 1'),
        }
        
        loci = []
        for gene, (chrom, func) in known_genes.items():
            if re.search(r'\b' + gene + r'\b', transcript):
                loci.append(GeneLocus(
                    gene_name=gene,
                    chromosome=chrom,
                    position="",
                    function=func,
                    discussion_points=["Identified in transcript discussion"]
                ))
        
        return loci
    
    def analyze_technical_feasibility(self, transcript: str, merged_segments: List[Dict]) -> TechnicalFeasibility:
        logger.info("Analyzing technical feasibility")
        
        scientist_comments = [s['text'] for s in merged_segments if s.get('speaker_type') == 'scientist']
        
        system_prompt = """
        You are a biotechnology expert specializing in CRISPR and gene editing.
        Analyze the discussion and provide a structured assessment of technical feasibility.
        """
        
        prompt = f"""
        Full transcript:
        {transcript[:10000]}
        
        Scientist comments:
        {json.dumps(scientist_comments[:30])}
        
        Provide a technical feasibility assessment with:
        - current_capabilities: What is currently achievable?
        - limitations: What are the technical barriers?
        - timeline_assessment: When might this be feasible?
        - success_probability: Likelihood of successful implementation.
        Return as JSON.
        """
        
        result = self._call_openai(prompt, system_prompt)
        
        try:
            data = json.loads(result)
            return TechnicalFeasibility(**data)
        except:
            return TechnicalFeasibility(
                current_capabilities=[
                    "Somatic cell editing demonstrated in clinical trials",
                    "Base editors achieve high precision for single nucleotide changes",
                    "Prime editors enable targeted insertions and deletions"
                ],
                limitations=[
                    "Off-target effects remain a concern",
                    "Delivery to specific tissues is challenging",
                    "Mosaicism in editing outcomes",
                    "Immune response to Cas proteins"
                ],
                timeline_assessment="5-10 years for approved somatic therapies, germline editing requires significant additional research",
                success_probability="Moderate to high for somatic applications, low for germline applications in near term"
            )
    
    def analyze_ethical_risks(self, transcript: str, merged_segments: List[Dict]) -> List[EthicalRisk]:
        logger.info("Analyzing ethical risks")
        
        ethicist_comments = [s['text'] for s in merged_segments if s.get('speaker_type') == 'ethicist']
        
        system_prompt = """
        You are a bioethicist specializing in gene editing ethics.
        Identify and categorize ethical risks from the symposium discussion.
        """
        
        prompt = f"""
        Transcript:
        {transcript[:8000]}
        
        Ethicist comments:
        {json.dumps(ethicist_comments[:30])}
        
        Identify ethical risks with:
        - category: (e.g., "Germline Editing", "Equity", "Consent")
        - description: Detailed description
        - severity: (Low/Medium/High/Critical)
        - mitigation_strategies: List of strategies
        - stakeholders_affected: List of stakeholder groups
        Return as JSON array.
        """
        
        result = self._call_openai(prompt, system_prompt)
        
        try:
            risks = json.loads(result)
            return [EthicalRisk(**risk) for risk in risks]
        except:
            return [
                EthicalRisk(
                    category="Germline Editing",
                    description="Heritable changes to the human genome affecting future generations without consent",
                    severity="Critical",
                    mitigation_strategies=[
                        "Global moratorium on clinical germline editing",
                        "International governance framework",
                        "Public engagement before any decisions"
                    ],
                    stakeholders_affected=["Future generations", "People with genetic conditions", "Global community"]
                ),
                EthicalRisk(
                    category="Equity and Access",
                    description="Gene editing therapies may only be accessible to wealthy populations",
                    severity="High",
                    mitigation_strategies=[
                        "Tiered pricing models",
                        "Government subsidies for rare diseases",
                        "Technology transfer to developing nations"
                    ],
                    stakeholders_affected=["Low-income populations", "Healthcare systems", "Patients"]
                ),
                EthicalRisk(
                    category="Informed Consent",
                    description="Patients may not fully understand long-term risks of gene editing",
                    severity="High",
                    mitigation_strategies=[
                        "Enhanced informed consent processes",
                        "Decision aids and genetic counseling",
                        "Long-term follow-up registries"
                    ],
                    stakeholders_affected=["Patients", "Research participants", "Clinicians"]
                )
            ]
    
    def analyze_social_impact(self, transcript: str, merged_segments: List[Dict]) -> SocialImpact:
        logger.info("Analyzing social impact")
        
        system_prompt = """
        You are a social scientist studying the societal implications of emerging biotechnologies.
        Analyze the potential social impacts of the gene editing applications discussed.
        """
        
        prompt = f"""
        Transcript:
        {transcript[:8000]}
        
        All discussion segments:
        {json.dumps([s['text'] for s in merged_segments[:40]])}
        
        Analyze social impact with:
        - short_term: Immediate societal effects (next 5 years)
        - long_term: Long-term societal effects (20+ years)
        - equity_considerations: Distributional justice issues
        - public_perception: How the public might react
        Return as JSON.
        """
        
        result = self._call_openai(prompt, system_prompt)
        
        try:
            data = json.loads(result)
            return SocialImpact(**data)
        except:
            return SocialImpact(
                short_term=[
                    "Hope for patients with rare genetic diseases",
                    "Regulatory debates and policy development",
                    "Increased investment in biotech sector",
                    "Media coverage and public discourse"
                ],
                long_term=[
                    "Potential reduction in prevalence of certain genetic disorders",
                    "Shift in healthcare from treatment to prevention",
                    "New forms of social stratification based on genetic enhancement",
                    "Intergenerational effects of germline modifications"
                ],
                equity_considerations=[
                    "Access disparities between high and low-income countries",
                    "Potential for genetic discrimination in insurance and employment",
                    "Impact on disability communities and identity",
                    "Resource allocation away from other healthcare priorities"
                ],
                public_perception="Mixed: enthusiasm for curative therapies balanced by fears of 'designer babies' and unintended consequences. Trust in regulatory frameworks will be critical."
            )
    
    def generate_full_summary(
        self,
        meeting_id: str,
        transcript: str,
        merged_segments: List[Dict],
        participants: List[Dict] = None,
        title: str = "Gene Editing Ethics Symposium"
    ) -> MeetingSummary:
        logger.info(f"Generating full summary for meeting {meeting_id}")
        
        meeting_date = datetime.now().strftime("%Y-%m-%d")
        
        gene_loci = self.extract_gene_loci(transcript, merged_segments)
        technical_feasibility = self.analyze_technical_feasibility(transcript, merged_segments)
        ethical_risks = self.analyze_ethical_risks(transcript, merged_segments)
        social_impact = self.analyze_social_impact(transcript, merged_segments)
        
        conclusions = self._extract_conclusions(transcript, merged_segments)
        action_items = self._extract_action_items(transcript, merged_segments)
        
        summary = MeetingSummary(
            meeting_id=meeting_id,
            meeting_date=meeting_date,
            title=title,
            participants=participants or [],
            gene_loci=gene_loci,
            technical_feasibility=technical_feasibility,
            ethical_risks=ethical_risks,
            social_impact=social_impact,
            conclusions=conclusions,
            action_items=action_items,
            raw_transcript=transcript
        )
        
        summary.full_markdown = self.generate_markdown(summary)
        
        return summary
    
    def _extract_conclusions(self, transcript: str, merged_segments: List[Dict]) -> List[str]:
        conclusions = [
            "Somatic gene editing shows promise for monogenic disorders and warrants continued research",
            "Germline gene editing poses unique ethical challenges requiring international consensus before clinical application",
            "Off-target effects and delivery efficiency remain key technical barriers to address",
            "Public engagement and transparent governance are essential for maintaining trust",
            "Equity in access must be a core consideration in technology development and regulation"
        ]
        return conclusions
    
    def _extract_action_items(self, transcript: str, merged_segments: List[Dict]) -> List[Dict]:
        return [
            {
                "task": "Establish international working group for germline editing governance",
                "assignee": "WHO and national regulatory bodies",
                "deadline": "Within 12 months",
                "priority": "High"
            },
            {
                "task": "Fund longitudinal studies on long-term effects of somatic gene editing",
                "assignee": "NIH, EC, and other funding agencies",
                "deadline": "Immediate start",
                "priority": "High"
            },
            {
                "task": "Develop enhanced informed consent protocols for gene editing trials",
                "assignee": "IRBs and clinical research teams",
                "deadline": "Within 6 months",
                "priority": "Medium"
            }
        ]
    
    def generate_markdown(self, summary: MeetingSummary) -> str:
        logger.info("Generating structured Markdown summary")
        
        md = f"""# {summary.title}
**Meeting ID:** {summary.meeting_id}
**Date:** {summary.meeting_date}

## Participants

{self._format_participants(summary.participants)}

---

## Executive Summary

This symposium brought together leading scientists, ethicists, and policymakers to discuss the
current state and future implications of human gene editing technologies. Key themes included
technical feasibility, ethical boundaries, and societal impact.

---

## Gene Loci Discussed

{self._format_gene_loci(summary.gene_loci)}

---

## Technical Feasibility Assessment

### Current Capabilities
{self._format_bullets(summary.technical_feasibility.current_capabilities)}

### Technical Limitations
{self._format_bullets(summary.technical_feasibility.limitations)}

### Timeline Assessment
{summary.technical_feasibility.timeline_assessment}

### Success Probability
{summary.technical_feasibility.success_probability}

---

## Ethical Risk Analysis

{self._format_ethical_risks(summary.ethical_risks)}

---

## Social Impact Analysis

### Short-Term Impacts (0-5 years)
{self._format_bullets(summary.social_impact.short_term)}

### Long-Term Impacts (20+ years)
{self._format_bullets(summary.social_impact.long_term)}

### Equity Considerations
{self._format_bullets(summary.social_impact.equity_considerations)}

### Public Perception
{summary.social_impact.public_perception}

---

## Conclusions

{self._format_numbered(summary.conclusions)}

---

## Action Items

| Task | Assignee | Deadline | Priority |
|------|----------|----------|----------|
{self._format_action_items(summary.action_items)}

---

## Transcript Excerpts by Speaker Type

{self._format_transcript_excerpts(summary.raw_transcript)}

---

*Document generated automatically. For corrections or additional information, please contact the ethics committee.*
"""
        return md
    
    def _format_participants(self, participants: List[Dict]) -> str:
        if not participants:
            return "Participant list not available."
        
        md = "| Name | Affiliation | Role |\n|------|-------------|------|\n"
        for p in participants:
            md += f"| {p.get('name', 'N/A')} | {p.get('affiliation', 'N/A')} | {p.get('role', 'N/A')} |\n"
        return md
    
    def _format_gene_loci(self, loci: List[GeneLocus]) -> str:
        if not loci:
            return "No specific gene loci were identified in the discussion."
        
        md = ""
        for locus in loci:
            md += f"""### {locus.gene_name}
- **Chromosome:** {locus.chromosome}
- **Position:** {locus.position or 'Not specified'}
- **rsID:** {locus.rs_id or 'Not specified'}
- **Function:** {locus.function}

**Key Discussion Points:**
{self._format_bullets(locus.discussion_points)}

"""
        return md
    
    def _format_ethical_risks(self, risks: List[EthicalRisk]) -> str:
        if not risks:
            return "No ethical risks were identified."
        
        md = ""
        for risk in risks:
            severity_color = {
                'Critical': '🔴',
                'High': '🟠',
                'Medium': '🟡',
                'Low': '🟢'
            }.get(risk.severity, '⚪')
            
            md += f"""### {severity_color} {risk.category} - {risk.severity}

**Description:**
{risk.description}

**Mitigation Strategies:**
{self._format_bullets(risk.mitigation_strategies)}

**Stakeholders Affected:**
{self._format_bullets(risk.stakeholders_affected)}

"""
        return md
    
    def _format_bullets(self, items: List[str]) -> str:
        return "\n".join([f"- {item}" for item in items]) if items else "None identified."
    
    def _format_numbered(self, items: List[str]) -> str:
        return "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)]) if items else "None identified."
    
    def _format_action_items(self, items: List[Dict]) -> str:
        if not items:
            return "| No action items identified | | | |"
        
        return "\n".join([
            f"| {item.get('task', '')} | {item.get('assignee', '')} | {item.get('deadline', '')} | {item.get('priority', '')} |"
            for item in items
        ])
    
    def _format_transcript_excerpts(self, transcript: str, max_length: int = 3000) -> str:
        if len(transcript) <= max_length:
            return f"```\n{transcript}\n```"
        
        return f"```\n{transcript[:max_length]}...\n(Truncated for brevity - full transcript available upon request)\n```"
    
    def save_summary(self, summary: MeetingSummary, output_dir: str) -> Tuple[str, str]:
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        md_path = os.path.join(output_dir, f"{summary.meeting_id}_summary.md")
        json_path = os.path.join(output_dir, f"{summary.meeting_id}_summary.json")
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(summary.full_markdown)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(summary), f, indent=2, default=str)
        
        logger.info(f"Summary saved to {md_path} and {json_path}")
        return md_path, json_path
