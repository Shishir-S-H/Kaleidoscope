# Code Examples for Backend Integration

**Complete Java Spring Boot Code Examples for Kaleidoscope AI Integration**

---

## 📋 Overview

This document provides complete, production-ready code examples for integrating Kaleidoscope AI services into your Spring Boot application. All examples include error handling, logging, and best practices.

---

## 🏗️ Project Structure

```
src/main/java/com/yourcompany/kaleidoscope/
├── config/
│   ├── RedisConfig.java
│   └── ElasticsearchConfig.java
├── dto/
│   ├── ImageProcessingJob.java
│   ├── MLInsightsResult.java
│   ├── FaceDetectionResult.java
│   └── PostInsightsEnriched.java
├── entity/
│   ├── MediaSearchReadModel.java
│   ├── PostSearchReadModel.java
│   └── UserSearchReadModel.java
├── repository/
│   ├── MediaSearchReadModelRepository.java
│   ├── PostSearchReadModelRepository.java
│   └── UserSearchReadModelRepository.java
├── service/
│   ├── RedisStreamPublisher.java
│   ├── MLInsightsConsumer.java
│   └── SearchService.java
├── controller/
│   └── SearchController.java
└── KaleidoscopeApplication.java
```

---

## ⚙️ Configuration Classes

### Redis Configuration

```java
// RedisConfig.java
@Configuration
@EnableRedisRepositories
@Slf4j
public class RedisConfig {
    
    @Value("${spring.redis.host:localhost}")
    private String redisHost;
    
    @Value("${spring.redis.port:6379}")
    private int redisPort;
    
    @Value("${spring.redis.timeout:2000}")
    private int timeout;
    
    @Bean
    public LettuceConnectionFactory redisConnectionFactory() {
        RedisStandaloneConfiguration config = new RedisStandaloneConfiguration();
        config.setHostName(redisHost);
        config.setPort(redisPort);
        config.setDatabase(0);
        
        LettuceClientConfiguration clientConfig = LettuceClientConfiguration.builder()
            .commandTimeout(Duration.ofMillis(timeout))
            .build();
        
        return new LettuceConnectionFactory(config, clientConfig);
    }
    
    @Bean
    public RedisTemplate<String, Object> redisTemplate() {
        RedisTemplate<String, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(redisConnectionFactory());
        
        // Configure serializers
        template.setKeySerializer(new StringRedisSerializer());
        template.setHashKeySerializer(new StringRedisSerializer());
        template.setValueSerializer(new GenericJackson2JsonRedisSerializer());
        template.setHashValueSerializer(new GenericJackson2JsonRedisSerializer());
        
        template.afterPropertiesSet();
        return template;
    }
    
    @Bean
    public StreamMessageListenerContainer<String, Object> streamMessageListenerContainer() {
        StreamMessageListenerContainer.StreamMessageListenerContainerOptions<String, Object> options = 
            StreamMessageListenerContainer.StreamMessageListenerContainerOptions
                .builder()
                .pollTimeout(Duration.ofMillis(1000))
                .build();
        
        return StreamMessageListenerContainer.create(redisConnectionFactory(), options);
    }
}
```

### Elasticsearch Configuration

```java
// ElasticsearchConfig.java
@Configuration
@EnableElasticsearchRepositories
@Slf4j
public class ElasticsearchConfig {
    
    @Value("${spring.elasticsearch.uris:http://localhost:9200}")
    private String elasticsearchUrl;
    
    @Value("${spring.elasticsearch.username:elastic}")
    private String username;
    
    @Value("${spring.elasticsearch.password:}")
    private String password;
    
    @Bean
    public ElasticsearchClient elasticsearchClient() {
        RestClientBuilder builder = RestClient.builder(
            HttpHost.create(elasticsearchUrl)
        );
        
        // Add authentication if provided
        if (StringUtils.hasText(username) && StringUtils.hasText(password)) {
            CredentialsProvider credentialsProvider = new BasicCredentialsProvider();
            credentialsProvider.setCredentials(
                AuthScope.ANY,
                new UsernamePasswordCredentials(username, password)
            );
            
            builder.setHttpClientConfigCallback(httpClientBuilder ->
                httpClientBuilder.setDefaultCredentialsProvider(credentialsProvider)
            );
        }
        
        RestClient restClient = builder.build();
        ElasticsearchTransport transport = new RestClientTransport(restClient, new JacksonJsonpMapper());
        
        return new ElasticsearchClient(transport);
    }
}
```

---

## 📊 DTOs (Data Transfer Objects)

### Image Processing Job

```java
// ImageProcessingJob.java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ImageProcessingJob {
    
    @NotBlank
    private String jobId;
    
    @NotNull
    private UUID postId;
    
    @NotNull
    private UUID mediaId;
    
    @NotNull
    private UUID userId;
    
    @NotBlank
    @URL
    private String imageUrl;
    
    private Long timestamp;
    
    @PrePersist
    public void prePersist() {
        if (timestamp == null) {
            timestamp = System.currentTimeMillis();
        }
    }
}
```

### ML Insights Result

```java
// MLInsightsResult.java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class MLInsightsResult {
    
    @NotBlank
    private String jobId;
    
    @NotNull
    private UUID postId;
    
    @NotNull
    private UUID mediaId;
    
    @NotNull
    private UUID userId;
    
    @NotBlank
    private String serviceType;
    
    @NotNull
    private MLResults results;
    
    private Long timestamp;
    
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class MLResults {
        private ContentModerationResult contentModeration;
        private ImageTaggingResult imageTagging;
        private SceneRecognitionResult sceneRecognition;
        private ImageCaptioningResult imageCaptioning;
    }
    
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class ContentModerationResult {
        private Boolean isSafe;
        private Float confidence;
    }
    
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class ImageTaggingResult {
        private List<String> tags;
        private List<Float> confidences;
    }
    
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class SceneRecognitionResult {
        private List<String> scenes;
        private List<Float> confidences;
    }
    
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class ImageCaptioningResult {
        private String caption;
        private Float confidence;
    }
}
```

### Face Detection Result

```java
// FaceDetectionResult.java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class FaceDetectionResult {
    
    @NotBlank
    private String jobId;
    
    @NotNull
    private UUID postId;
    
    @NotNull
    private UUID mediaId;
    
    @NotNull
    private UUID userId;
    
    @NotNull
    private List<FaceDetection> faces;
    
    private Long timestamp;
    
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class FaceDetection {
        private String faceId;
        private List<Float> boundingBox;
        private List<Float> embedding;
        private Float confidence;
    }
}
```

### Post Insights Enriched

```java
// PostInsightsEnriched.java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PostInsightsEnriched {
    
    @NotNull
    private UUID postId;
    
    @NotNull
    private UUID userId;
    
    @NotNull
    private List<String> aggregatedTags;
    
    @NotBlank
    private String eventType;
    
    @Min(0)
    private Integer totalMediaCount;
    
    @Min(0)
    private Integer totalFaceCount;
    
    @NotNull
    private Boolean isSafe;
    
    @NotNull
    private List<MediaInsight> mediaInsights;
    
    private Long timestamp;
    
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class MediaInsight {
        private UUID mediaId;
        private String caption;
        private List<String> tags;
        private List<String> scenes;
        private Boolean isSafe;
        private Float confidenceScore;
        private Integer faceCount;
    }
}
```

---

## 🗄️ JPA Entities

### Media Search Read Model

```java
// MediaSearchReadModel.java
@Entity
@Table(name = "media_search_read_model")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class MediaSearchReadModel {
    
    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private UUID id;
    
    @Column(name = "post_id", nullable = false)
    private UUID postId;
    
    @Column(name = "media_id", nullable = false)
    private UUID mediaId;
    
    @Column(name = "user_id", nullable = false)
    private UUID userId;
    
    @Column(name = "caption", columnDefinition = "TEXT")
    private String caption;
    
    @ElementCollection
    @CollectionTable(name = "media_search_tags", joinColumns = @JoinColumn(name = "media_id"))
    @Column(name = "tag")
    private List<String> tags = new ArrayList<>();
    
    @ElementCollection
    @CollectionTable(name = "media_search_scenes", joinColumns = @JoinColumn(name = "media_id"))
    @Column(name = "scene")
    private List<String> scenes = new ArrayList<>();
    
    @Column(name = "is_safe", nullable = false)
    private Boolean isSafe = true;
    
    @Column(name = "confidence_score")
    private Float confidenceScore;
    
    @Column(name = "face_count")
    private Integer faceCount = 0;
    
    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
    
    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
```

### Post Search Read Model

```java
// PostSearchReadModel.java
@Entity
@Table(name = "post_search_read_model")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PostSearchReadModel {
    
    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private UUID id;
    
    @Column(name = "post_id", nullable = false, unique = true)
    private UUID postId;
    
    @Column(name = "user_id", nullable = false)
    private UUID userId;
    
    @ElementCollection
    @CollectionTable(name = "post_search_tags", joinColumns = @JoinColumn(name = "post_id"))
    @Column(name = "tag")
    private List<String> aggregatedTags = new ArrayList<>();
    
    @Column(name = "event_type", length = 100)
    private String eventType;
    
    @Column(name = "total_media_count")
    private Integer totalMediaCount = 0;
    
    @Column(name = "total_face_count")
    private Integer totalFaceCount = 0;
    
    @Column(name = "is_safe", nullable = false)
    private Boolean isSafe = true;
    
    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
    
    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
```

### User Search Read Model

```java
// UserSearchReadModel.java
@Entity
@Table(name = "user_search_read_model")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserSearchReadModel {
    
    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private UUID id;
    
    @Column(name = "user_id", nullable = false, unique = true)
    private UUID userId;
    
    @Column(name = "username", nullable = false, length = 255)
    private String username;
    
    @Column(name = "display_name", length = 255)
    private String displayName;
    
    @Column(name = "department", length = 100)
    private String department;
    
    @ElementCollection
    @CollectionTable(name = "user_search_interests", joinColumns = @JoinColumn(name = "user_id"))
    @Column(name = "interest")
    private List<String> interests = new ArrayList<>();
    
    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
    
    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
```

---

## 🗃️ JPA Repositories

### Media Search Repository

```java
// MediaSearchReadModelRepository.java
@Repository
public interface MediaSearchReadModelRepository extends JpaRepository<MediaSearchReadModel, UUID> {
    
    List<MediaSearchReadModel> findByPostId(UUID postId);
    
    List<MediaSearchReadModel> findByUserIdAndIsSafeTrue(UUID userId);
    
    List<MediaSearchReadModel> findByTagsIn(List<String> tags);
    
    List<MediaSearchReadModel> findByScenesIn(List<String> scenes);
    
    @Query("SELECT m FROM MediaSearchReadModel m WHERE m.userId = :userId AND m.isSafe = true ORDER BY m.createdAt DESC")
    List<MediaSearchReadModel> findRecentSafeMediaByUser(@Param("userId") UUID userId, Pageable pageable);
    
    @Query("SELECT m FROM MediaSearchReadModel m WHERE m.tags IN :tags AND m.isSafe = true")
    List<MediaSearchReadModel> findSafeMediaByTags(@Param("tags") List<String> tags);
    
    @Query("SELECT m FROM MediaSearchReadModel m WHERE m.scenes IN :scenes AND m.isSafe = true")
    List<MediaSearchReadModel> findSafeMediaByScenes(@Param("scenes") List<String> scenes);
    
    @Query("SELECT m FROM MediaSearchReadModel m WHERE m.caption LIKE %:query% AND m.isSafe = true")
    List<MediaSearchReadModel> searchByCaption(@Param("query") String query);
    
    @Modifying
    @Query("DELETE FROM MediaSearchReadModel m WHERE m.postId = :postId")
    void deleteByPostId(@Param("postId") UUID postId);
}
```

### Post Search Repository

```java
// PostSearchReadModelRepository.java
@Repository
public interface PostSearchReadModelRepository extends JpaRepository<PostSearchReadModel, UUID> {
    
    Optional<PostSearchReadModel> findByPostId(UUID postId);
    
    List<PostSearchReadModel> findByUserIdAndIsSafeTrue(UUID userId);
    
    List<PostSearchReadModel> findByEventType(String eventType);
    
    List<PostSearchReadModel> findByAggregatedTagsIn(List<String> tags);
    
    @Query("SELECT p FROM PostSearchReadModel p WHERE p.userId = :userId AND p.isSafe = true ORDER BY p.createdAt DESC")
    List<PostSearchReadModel> findRecentSafePostsByUser(@Param("userId") UUID userId, Pageable pageable);
    
    @Query("SELECT p FROM PostSearchReadModel p WHERE p.aggregatedTags IN :tags AND p.isSafe = true")
    List<PostSearchReadModel> findSafePostsByTags(@Param("tags") List<String> tags);
    
    @Query("SELECT p FROM PostSearchReadModel p WHERE p.eventType = :eventType AND p.isSafe = true")
    List<PostSearchReadModel> findSafePostsByEventType(@Param("eventType") String eventType);
    
    @Modifying
    @Query("DELETE FROM PostSearchReadModel p WHERE p.postId = :postId")
    void deleteByPostId(@Param("postId") UUID postId);
}
```

### User Search Repository

```java
// UserSearchReadModelRepository.java
@Repository
public interface UserSearchReadModelRepository extends JpaRepository<UserSearchReadModel, UUID> {
    
    Optional<UserSearchReadModel> findByUserId(UUID userId);
    
    Optional<UserSearchReadModel> findByUsername(String username);
    
    List<UserSearchReadModel> findByDepartment(String department);
    
    List<UserSearchReadModel> findByInterestsIn(List<String> interests);
    
    @Query("SELECT u FROM UserSearchReadModel u WHERE u.username LIKE %:query% OR u.displayName LIKE %:query%")
    List<UserSearchReadModel> searchByUsernameOrDisplayName(@Param("query") String query);
    
    @Query("SELECT u FROM UserSearchReadModel u WHERE u.interests IN :interests")
    List<UserSearchReadModel> findByInterests(@Param("interests") List<String> interests);
}
```

---

## 🔄 Redis Streams Services

### Redis Stream Publisher

```java
// RedisStreamPublisher.java
@Service
@Slf4j
public class RedisStreamPublisher {
    
    @Autowired
    private RedisTemplate<String, Object> redisTemplate;
    
    @Value("${kaleidoscope.redis.streams.post-image-processing}")
    private String postImageProcessingStream;
    
    @Value("${kaleidoscope.redis.streams.es-sync-queue}")
    private String esSyncQueueStream;
    
    public void publishImageProcessingJob(ImageProcessingJob job) {
        try {
            Map<String, Object> message = Map.of(
                "jobId", job.getJobId(),
                "postId", job.getPostId().toString(),
                "mediaId", job.getMediaId().toString(),
                "userId", job.getUserId().toString(),
                "imageUrl", job.getImageUrl(),
                "timestamp", job.getTimestamp()
            );
            
            String messageId = redisTemplate.opsForStream()
                .add(postImageProcessingStream, message)
                .getValue();
            
            log.info("Published image processing job: {} with message ID: {}", 
                job.getJobId(), messageId);
            
        } catch (Exception e) {
            log.error("Failed to publish image processing job: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to publish job", e);
        }
    }
    
    public void publishESSyncMessage(ESSyncMessage message) {
        try {
            Map<String, Object> payload = Map.of(
                "tableName", message.getTableName(),
                "operation", message.getOperation(),
                "recordId", message.getRecordId(),
                "data", message.getData(),
                "timestamp", System.currentTimeMillis()
            );
            
            String messageId = redisTemplate.opsForStream()
                .add(esSyncQueueStream, payload)
                .getValue();
            
            log.info("Published ES sync message for table: {} with message ID: {}", 
                message.getTableName(), messageId);
            
        } catch (Exception e) {
            log.error("Failed to publish ES sync message: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to publish ES sync", e);
        }
    }
}
```

### ML Insights Consumer

```java
// MLInsightsConsumer.java
@Service
@Slf4j
public class MLInsightsConsumer {
    
    @Autowired
    private MediaSearchReadModelRepository mediaSearchRepo;
    
    @Autowired
    private PostSearchReadModelRepository postSearchRepo;
    
    @Autowired
    private RedisStreamPublisher redisPublisher;
    
    @Value("${kaleidoscope.redis.streams.ml-insights-results}")
    private String mlInsightsResultsStream;
    
    @Value("${kaleidoscope.redis.streams.face-detection-results}")
    private String faceDetectionResultsStream;
    
    @Value("${kaleidoscope.redis.streams.post-insights-enriched}")
    private String postInsightsEnrichedStream;
    
    @StreamListener(target = mlInsightsResultsStream)
    public void handleMLInsights(Map<String, Object> message) {
        try {
            log.info("Received ML insights message: {}", message);
            
            MLInsightsResult result = mapToMLInsightsResult(message);
            
            // Update media search read model
            updateMediaSearchReadModel(result);
            
            // Check if all media in post are processed
            if (isPostComplete(result.getPostId())) {
                // Trigger post aggregation
                triggerPostAggregation(result.getPostId());
            }
            
        } catch (Exception e) {
            log.error("Failed to process ML insights: {}", e.getMessage(), e);
        }
    }
    
    @StreamListener(target = faceDetectionResultsStream)
    public void handleFaceDetection(Map<String, Object> message) {
        try {
            log.info("Received face detection message: {}", message);
            
            FaceDetectionResult result = mapToFaceDetectionResult(message);
            
            // Update face search read model
            updateFaceSearchReadModel(result);
            
        } catch (Exception e) {
            log.error("Failed to process face detection: {}", e.getMessage(), e);
        }
    }
    
    @StreamListener(target = postInsightsEnrichedStream)
    public void handlePostInsights(Map<String, Object> message) {
        try {
            log.info("Received post insights message: {}", message);
            
            PostInsightsEnriched result = mapToPostInsightsEnriched(message);
            
            // Update post search read model
            updatePostSearchReadModel(result);
            
            // Trigger ES sync
            triggerESSync(result);
            
        } catch (Exception e) {
            log.error("Failed to process post insights: {}", e.getMessage(), e);
        }
    }
    
    private MLInsightsResult mapToMLInsightsResult(Map<String, Object> message) {
        return MLInsightsResult.builder()
            .jobId((String) message.get("jobId"))
            .postId(UUID.fromString((String) message.get("postId")))
            .mediaId(UUID.fromString((String) message.get("mediaId")))
            .userId(UUID.fromString((String) message.get("userId")))
            .serviceType((String) message.get("serviceType"))
            .results(mapToMLResults((Map<String, Object>) message.get("results")))
            .timestamp((Long) message.get("timestamp"))
            .build();
    }
    
    private MLInsightsResult.MLResults mapToMLResults(Map<String, Object> results) {
        return MLInsightsResult.MLResults.builder()
            .contentModeration(mapToContentModeration((Map<String, Object>) results.get("contentModeration")))
            .imageTagging(mapToImageTagging((Map<String, Object>) results.get("imageTagging")))
            .sceneRecognition(mapToSceneRecognition((Map<String, Object>) results.get("sceneRecognition")))
            .imageCaptioning(mapToImageCaptioning((Map<String, Object>) results.get("imageCaptioning")))
            .build();
    }
    
    private void updateMediaSearchReadModel(MLInsightsResult result) {
        // Find existing record or create new one
        MediaSearchReadModel existing = mediaSearchRepo.findByPostIdAndMediaId(result.getPostId(), result.getMediaId())
            .orElse(MediaSearchReadModel.builder()
                .postId(result.getPostId())
                .mediaId(result.getMediaId())
                .userId(result.getUserId())
                .build());
        
        // Update based on service type
        switch (result.getServiceType()) {
            case "content_moderation":
                if (result.getResults().getContentModeration() != null) {
                    existing.setIsSafe(result.getResults().getContentModeration().getIsSafe());
                    existing.setConfidenceScore(result.getResults().getContentModeration().getConfidence());
                }
                break;
            case "image_tagger":
                if (result.getResults().getImageTagging() != null) {
                    existing.setTags(result.getResults().getImageTagging().getTags());
                }
                break;
            case "scene_recognition":
                if (result.getResults().getSceneRecognition() != null) {
                    existing.setScenes(result.getResults().getSceneRecognition().getScenes());
                }
                break;
            case "image_captioning":
                if (result.getResults().getImageCaptioning() != null) {
                    existing.setCaption(result.getResults().getImageCaptioning().getCaption());
                }
                break;
        }
        
        mediaSearchRepo.save(existing);
    }
    
    private void updatePostSearchReadModel(PostInsightsEnriched result) {
        PostSearchReadModel model = postSearchRepo.findByPostId(result.getPostId())
            .orElse(PostSearchReadModel.builder()
                .postId(result.getPostId())
                .userId(result.getUserId())
                .build());
        
        model.setAggregatedTags(result.getAggregatedTags());
        model.setEventType(result.getEventType());
        model.setTotalMediaCount(result.getTotalMediaCount());
        model.setTotalFaceCount(result.getTotalFaceCount());
        model.setIsSafe(result.getIsSafe());
        
        postSearchRepo.save(model);
    }
    
    private void triggerESSync(PostInsightsEnriched result) {
        ESSyncMessage message = ESSyncMessage.builder()
            .tableName("post_search_read_model")
            .operation("INSERT")
            .recordId(result.getPostId().toString())
            .data(result)
            .build();
        
        redisPublisher.publishESSyncMessage(message);
    }
    
    private boolean isPostComplete(UUID postId) {
        // Implementation depends on your post structure
        // This is a simplified example
        return true;
    }
    
    private void triggerPostAggregation(UUID postId) {
        // Implementation to trigger post aggregation
        // This would typically involve publishing a message
    }
}
```

---

## 🔍 Elasticsearch Services

### Search Service

```java
// SearchService.java
@Service
@Slf4j
public class SearchService {
    
    @Autowired
    private ElasticsearchClient elasticsearchClient;
    
    public List<MediaSearchDocument> searchMedia(String query, List<String> tags, List<String> scenes) {
        try {
            BoolQuery.Builder boolQuery = new BoolQuery.Builder();
            
            if (StringUtils.hasText(query)) {
                boolQuery.must(Query.of(q -> q.match(m -> m.field("caption").query(query))));
            }
            
            if (tags != null && !tags.isEmpty()) {
                boolQuery.must(Query.of(q -> q.terms(t -> t.field("tags").terms(terms -> 
                    terms.value(tags.stream().map(FieldValue::of).collect(Collectors.toList()))))));
            }
            
            if (scenes != null && !scenes.isEmpty()) {
                boolQuery.must(Query.of(q -> q.terms(t -> t.field("scenes").terms(terms -> 
                    terms.value(scenes.stream().map(FieldValue::of).collect(Collectors.toList()))))));
            }
            
            boolQuery.must(Query.of(q -> q.term(t -> t.field("isSafe").value(true))));
            
            SearchRequest searchRequest = SearchRequest.of(s -> s
                .index("media_search")
                .query(boolQuery.build()._toQuery())
                .size(20)
                .sort(sort -> sort.field(f -> f.field("createdAt").order(SortOrder.Desc)))
            );
            
            SearchResponse<MediaSearchDocument> response = elasticsearchClient.search(searchRequest, MediaSearchDocument.class);
            
            return response.hits().hits().stream()
                .map(hit -> hit.source())
                .collect(Collectors.toList());
                
        } catch (IOException e) {
            log.error("Failed to search media: {}", e.getMessage(), e);
            throw new RuntimeException("Search failed", e);
        }
    }
    
    public List<PostSearchDocument> searchPosts(String query, List<String> tags, String eventType) {
        try {
            BoolQuery.Builder boolQuery = new BoolQuery.Builder();
            
            if (StringUtils.hasText(query)) {
                boolQuery.must(Query.of(q -> q.multiMatch(m -> m
                    .fields("aggregatedTags", "eventType")
                    .query(query)
                )));
            }
            
            if (tags != null && !tags.isEmpty()) {
                boolQuery.must(Query.of(q -> q.terms(t -> t.field("aggregatedTags").terms(terms -> 
                    terms.value(tags.stream().map(FieldValue::of).collect(Collectors.toList()))))));
            }
            
            if (StringUtils.hasText(eventType)) {
                boolQuery.must(Query.of(q -> q.term(t -> t.field("eventType").value(eventType))));
            }
            
            boolQuery.must(Query.of(q -> q.term(t -> t.field("isSafe").value(true))));
            
            SearchRequest searchRequest = SearchRequest.of(s -> s
                .index("post_search")
                .query(boolQuery.build()._toQuery())
                .size(20)
                .sort(sort -> sort.field(f -> f.field("createdAt").order(SortOrder.Desc)))
            );
            
            SearchResponse<PostSearchDocument> response = elasticsearchClient.search(searchRequest, PostSearchDocument.class);
            
            return response.hits().hits().stream()
                .map(hit -> hit.source())
                .collect(Collectors.toList());
                
        } catch (IOException e) {
            log.error("Failed to search posts: {}", e.getMessage(), e);
            throw new RuntimeException("Search failed", e);
        }
    }
}
```

---

## 🎮 REST Controllers

### Search Controller

```java
// SearchController.java
@RestController
@RequestMapping("/api/search")
@Slf4j
public class SearchController {
    
    @Autowired
    private SearchService searchService;
    
    @GetMapping("/media")
    public ResponseEntity<List<MediaSearchDocument>> searchMedia(
            @RequestParam(required = false) String query,
            @RequestParam(required = false) List<String> tags,
            @RequestParam(required = false) List<String> scenes) {
        
        try {
            List<MediaSearchDocument> results = searchService.searchMedia(query, tags, scenes);
            return ResponseEntity.ok(results);
            
        } catch (Exception e) {
            log.error("Failed to search media: {}", e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }
    
    @GetMapping("/posts")
    public ResponseEntity<List<PostSearchDocument>> searchPosts(
            @RequestParam(required = false) String query,
            @RequestParam(required = false) List<String> tags,
            @RequestParam(required = false) String eventType) {
        
        try {
            List<PostSearchDocument> results = searchService.searchPosts(query, tags, eventType);
            return ResponseEntity.ok(results);
            
        } catch (Exception e) {
            log.error("Failed to search posts: {}", e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }
}
```

---

## 🧪 Test Classes

### Integration Test

```java
// KaleidoscopeIntegrationTest.java
@SpringBootTest
@Testcontainers
@Slf4j
public class KaleidoscopeIntegrationTest {
    
    @Container
    static GenericContainer<?> redis = new GenericContainer<>("redis:7-alpine")
            .withExposedPorts(6379);
    
    @Container
    static GenericContainer<?> elasticsearch = new GenericContainer<>("docker.elastic.co/elasticsearch/elasticsearch:8.10.2")
            .withExposedPorts(9200)
            .withEnv("discovery.type", "single-node")
            .withEnv("xpack.security.enabled", "false");
    
    @Autowired
    private RedisStreamPublisher redisStreamPublisher;
    
    @Autowired
    private SearchService searchService;
    
    @Test
    public void testImageProcessingFlow() {
        // Create test image processing job
        ImageProcessingJob job = ImageProcessingJob.builder()
            .jobId("test-job-1")
            .postId(UUID.randomUUID())
            .mediaId(UUID.randomUUID())
            .userId(UUID.randomUUID())
            .imageUrl("https://example.com/test-image.jpg")
            .build();
        
        // Publish job
        redisStreamPublisher.publishImageProcessingJob(job);
        
        // Wait for processing
        try {
            Thread.sleep(30000); // 30 seconds
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        
        // Verify results
        // This would depend on your specific test setup
        assertThat(job.getJobId()).isNotNull();
    }
    
    @Test
    public void testSearchFunctionality() {
        // Test search functionality
        List<MediaSearchDocument> results = searchService.searchMedia("beach", null, null);
        assertThat(results).isNotNull();
    }
}
```

---

## 🚀 Application Startup

### Main Application Class

```java
// KaleidoscopeApplication.java
@SpringBootApplication
@EnableJpaRepositories
@EnableElasticsearchRepositories
@EnableRedisRepositories
@Slf4j
public class KaleidoscopeApplication {
    
    public static void main(String[] args) {
        SpringApplication.run(KaleidoscopeApplication.class, args);
        log.info("Kaleidoscope AI Integration started successfully!");
    }
}
```

---

## 📝 Application Properties

### application.yml

```yaml
spring:
  application:
    name: kaleidoscope-ai-integration
  
  redis:
    host: localhost
    port: 6379
    timeout: 2000ms
    lettuce:
      pool:
        max-active: 8
        max-idle: 8
        min-idle: 0
  
  elasticsearch:
    uris: http://localhost:9200
    username: elastic
    password: your_elasticsearch_password
  
  datasource:
    url: jdbc:postgresql://localhost:5432/your_database
    username: your_username
    password: your_password
    driver-class-name: org.postgresql.Driver
  
  jpa:
    hibernate:
      ddl-auto: validate
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        format_sql: true
    show-sql: false
  
  jackson:
    default-property-inclusion: non_null
    serialization:
      write-dates-as-timestamps: false

# Custom configuration
kaleidoscope:
  redis:
    streams:
      post-image-processing: post-image-processing
      ml-insights-results: ml-insights-results
      face-detection-results: face-detection-results
      post-insights-enriched: post-insights-enriched
      es-sync-queue: es-sync-queue
  elasticsearch:
    indices:
      media-search: media_search
      post-search: post_search
      user-search: user_search
      face-search: face_search
      recommendations-knn: recommendations_knn
      feed-personalized: feed_personalized
      known-faces: known_faces_index

# Logging
logging:
  level:
    com.yourcompany.kaleidoscope: DEBUG
    org.springframework.data.redis: DEBUG
    org.elasticsearch: DEBUG
```

---

## 🔧 Maven Dependencies

### pom.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.7.18</version>
        <relativePath/>
    </parent>
    
    <groupId>com.yourcompany</groupId>
    <artifactId>kaleidoscope-ai-integration</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    
    <properties>
        <java.version>17</java.version>
        <elasticsearch.version>8.10.2</elasticsearch.version>
    </properties>
    
    <dependencies>
        <!-- Spring Boot Starters -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-redis</artifactId>
        </dependency>
        
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        
        <!-- Database -->
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        
        <!-- Elasticsearch -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-elasticsearch</artifactId>
        </dependency>
        
        <!-- JSON Processing -->
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
        </dependency>
        
        <!-- Testing -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
        
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>postgresql</artifactId>
            <scope>test</scope>
        </dependency>
        
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>elasticsearch</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

---

## 🎯 Usage Examples

### Publishing Image Processing Job

```java
@RestController
@RequestMapping("/api/images")
public class ImageController {
    
    @Autowired
    private RedisStreamPublisher redisStreamPublisher;
    
    @PostMapping("/process")
    public ResponseEntity<String> processImage(@RequestBody ImageUploadRequest request) {
        try {
            ImageProcessingJob job = ImageProcessingJob.builder()
                .jobId(UUID.randomUUID().toString())
                .postId(request.getPostId())
                .mediaId(request.getMediaId())
                .userId(request.getUserId())
                .imageUrl(request.getImageUrl())
                .build();
            
            redisStreamPublisher.publishImageProcessingJob(job);
            
            return ResponseEntity.ok("Image processing job submitted: " + job.getJobId());
            
        } catch (Exception e) {
            log.error("Failed to process image: {}", e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body("Failed to process image");
        }
    }
}
```

### Searching Content

```java
@RestController
@RequestMapping("/api/search")
public class SearchController {
    
    @Autowired
    private SearchService searchService;
    
    @GetMapping("/media")
    public ResponseEntity<SearchResponse<MediaSearchDocument>> searchMedia(
            @RequestParam(required = false) String query,
            @RequestParam(required = false) List<String> tags,
            @RequestParam(required = false) List<String> scenes,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        
        try {
            List<MediaSearchDocument> results = searchService.searchMedia(query, tags, scenes);
            
            SearchResponse<MediaSearchDocument> response = SearchResponse.<MediaSearchDocument>builder()
                .results(results)
                .total(results.size())
                .page(page)
                .size(size)
                .build();
            
            return ResponseEntity.ok(response);
            
        } catch (Exception e) {
            log.error("Failed to search media: {}", e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }
}
```

---

**Use these code examples as a foundation for your Kaleidoscope AI integration!** 🚀

All examples include proper error handling, logging, and follow Spring Boot best practices. Customize them according to your specific requirements and coding standards.
