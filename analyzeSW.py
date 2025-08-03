def analyze_strengths_and_weaknesses(interview_data, llm_model):
        """Analyze interview responses using the fine-tuned model"""

        # Format interview data for analysis
        interview_text = ""
        for question, answer in interview_data.items():
                interview_text += f"Q: {question}\nA: {answer}\n\n"

        prompt = f"""As an experienced visa officer, analyze the following interview responses and provide a comprehensive assessment:

{interview_text}

Provide analysis in the following format:

STRENGTHS:
- [List specific strengths demonstrated in the responses]

WEAKNESSES:
- [List areas of concern or weakness]

RECOMMENDATIONS:
- [Specific advice for improvement]

OVERALL ASSESSMENT:
- [Overall evaluation and visa recommendation rationale]"""

        try:
                response = llm_model.generate(prompt, max_tokens=1000, temperature=0.7)

                # Parse the structured response
                analysis = {
                        "strengths": [],
                        "weaknesses": [],
                        "recommendations": [],
                        "overall_assessment": ""
                }

                current_section = None
                lines = response.strip().split('\n')

                for line in lines:
                        line = line.strip()
                        if line.upper().startswith('STRENGTHS:'):
                                current_section = 'strengths'
                        elif line.upper().startswith('WEAKNESSES:'):
                                current_section = 'weaknesses'
                        elif line.upper().startswith('RECOMMENDATIONS:'):
                                current_section = 'recommendations'
                        elif line.upper().startswith('OVERALL ASSESSMENT:'):
                                current_section = 'overall_assessment'
                        elif line.startswith('-') and current_section in ['strengths', 'weaknesses', 'recommendations']:
                                analysis[current_section].append(line[1:].strip())
                        elif current_section == 'overall_assessment' and line:
                                analysis['overall_assessment'] += line + ' '

                analysis['overall_assessment'] = analysis['overall_assessment'].strip()

                return analysis

        except Exception as e:
                print(f"Error in analysis: {e}")
                return {
                        "strengths": ["Unable to analyze - technical error"],
                        "weaknesses": ["Analysis unavailable"],
                        "recommendations": ["Please retry analysis"],
                        "overall_assessment": "Technical error occurred during analysis"
                }
        