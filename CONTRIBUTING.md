# Contributing to Kaleidoscope AI

Thank you for your interest in contributing to Kaleidoscope AI! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites

- Docker Desktop
- Python 3.10+
- Git
- Basic understanding of microservices architecture

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/kaleidoscope-ai.git
   cd kaleidoscope-ai
   ```

2. **Environment Setup**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit .env with your HuggingFace API token
   # Get token from: https://huggingface.co/settings/tokens
   ```

3. **Start Development Environment**
   ```bash
   # Start all services
   docker compose up -d
   
   # Verify services are running
   docker compose ps
   ```

4. **Run Tests**
   ```bash
   # Automated tests
   python tests/test_end_to_end.py
   
   # Manual testing
   # Follow docs/testing/MANUAL_TESTING_GUIDE.md
   ```

## 📝 How to Contribute

### Reporting Bugs

1. Check existing issues first
2. Use the bug report template
3. Include:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Docker version, etc.)

### Suggesting Features

1. Check existing feature requests
2. Use the feature request template
3. Include:
   - Clear description
   - Use case and motivation
   - Proposed solution
   - Alternatives considered

### Code Contributions

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Your Changes**
   ```bash
   # Run all tests
   python tests/test_end_to_end.py
   
   # Test specific service
   docker compose logs service_name
   ```

4. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "Add: brief description of changes"
   ```

5. **Push and Create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

## 🏗️ Project Structure

```
kaleidoscope-ai/
├── services/                 # AI microservices
│   ├── content_moderation/   # NSFW detection
│   ├── face_recognition/     # Face detection & recognition
│   ├── image_captioning/     # Image-to-text generation
│   ├── image_tagger/         # Object detection & tagging
│   ├── scene_recognition/    # Scene classification
│   ├── post_aggregator/      # Multi-image insights
│   └── es_sync/             # Elasticsearch synchronization
├── shared/                   # Common utilities
├── docs/                     # Documentation
├── tests/                    # Test suites
└── es_mappings/             # Elasticsearch index definitions
```

## 🧪 Testing Guidelines

### Automated Testing

- All new features must include tests
- Run `python tests/test_end_to_end.py` before submitting
- Ensure all tests pass (currently 14 tests, 100% pass rate)

### Manual Testing

- Test with real images using the manual testing guide
- Verify Redis Streams message flow
- Check Elasticsearch indexing and search

### Test Data

- Use the provided test images in `tests/test_images/`
- Test with various image types (photos, graphics, documents)
- Test edge cases (very large images, unusual formats)

## 📚 Documentation

### Code Documentation

- Add docstrings to new functions
- Include type hints where appropriate
- Update README.md for significant changes

### API Documentation

- Document new Redis Stream message formats
- Update Elasticsearch mapping documentation
- Add examples for new features

## 🎯 Areas for Contribution

### High Priority

- [ ] Performance optimizations
- [ ] Additional AI model integrations
- [ ] Enhanced error handling
- [ ] Monitoring and observability

### Medium Priority

- [ ] Additional search features
- [ ] Batch processing capabilities
- [ ] Cloud deployment guides
- [ ] API rate limiting

### Low Priority

- [ ] UI improvements
- [ ] Additional test coverage
- [ ] Documentation improvements
- [ ] Code refactoring

## 🔧 Development Guidelines

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions focused and small

### Git Workflow

- Use descriptive commit messages
- Squash commits when appropriate
- Keep pull requests focused and small
- Reference issues in commit messages

### Docker Guidelines

- Keep Dockerfiles minimal and efficient
- Use multi-stage builds when appropriate
- Pin dependency versions
- Document any special requirements

## 🐛 Troubleshooting

### Common Issues

1. **Services not starting**: Check Docker Desktop is running
2. **Redis connection errors**: Verify Redis is running on port 6379
3. **Elasticsearch errors**: Check ES is running on port 9200
4. **HuggingFace API errors**: Verify API token is valid

### Getting Help

- Check existing issues and discussions
- Create a new issue with detailed information
- Join our community discussions
- Review the troubleshooting guide in docs/

## 📋 Pull Request Process

1. **Fork the repository**
2. **Create your feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes** and test thoroughly
4. **Commit your changes** (`git commit -m 'Add amazing feature'`)
5. **Push to the branch** (`git push origin feature/amazing-feature`)
6. **Open a Pull Request**

### PR Requirements

- [ ] All tests pass
- [ ] Code follows project style guidelines
- [ ] Documentation updated as needed
- [ ] Changes are backwards compatible
- [ ] PR description explains the changes

## 🎉 Recognition

Contributors will be recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation

## 📞 Contact

- **Issues**: [GitHub Issues](https://github.com/yourusername/kaleidoscope-ai/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/kaleidoscope-ai/discussions)
- **Email**: [your-email@example.com]

Thank you for contributing to Kaleidoscope AI! 🚀
