package com.theseus.api.domain.billing.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.CustomException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.billing.dto.request.BillingUsageCreateRequest;
import com.theseus.api.domain.billing.dto.request.BillingUsageMetricsRequest;
import com.theseus.api.domain.billing.dto.response.BillingUsageResponse;
import com.theseus.api.domain.billing.entity.BillingUsage;
import com.theseus.api.domain.billing.repository.BillingUsageRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.time.LocalDateTime;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class BillingUsageServiceTest {

	private static final Long USER_ID = 3L;
	private static final Long PROJECT_ID = 7L;
	private static final Long BILLING_USAGE_ID = 11L;
	private static final String IDEMPOTENCY_KEY = "billing-usage-1";
	private static final String REPORTED_AT_TEXT = "2026-05-06T10:20:30";
	private static final LocalDateTime REPORTED_AT = LocalDateTime.of(2026, 5, 6, 10, 20, 30);
	private static final LocalDateTime CREATED_AT = LocalDateTime.of(2026, 5, 6, 10, 21, 0);

	@Mock
	private BillingUsageRepository billingUsageRepository;

	@Mock
	private UserRepository userRepository;

	@Mock
	private ProjectRepository projectRepository;

	private BillingUsageService billingUsageService;
	private User user;
	private Project project;

	@BeforeEach
	void setUp() {
		billingUsageService = new BillingUsageService(
			billingUsageRepository,
			userRepository,
			projectRepository,
			new ObjectMapper()
		);
		user = createUser();
		project = createProject(user);
	}

	@Test
	@DisplayName("정상 사용량 payload를 받으면 BillingUsage를 저장한다.")
	void createUsage() {
		// Given
		BillingUsageCreateRequest request = createRequest(120L, 30L, 150L, "gpt-test", REPORTED_AT_TEXT);
		when(billingUsageRepository.findByIdempotencyKey(IDEMPOTENCY_KEY)).thenReturn(Optional.empty());
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(billingUsageRepository.save(any(BillingUsage.class))).thenAnswer(invocation -> {
			BillingUsage billingUsage = invocation.getArgument(0);
			ReflectionTestUtils.setField(billingUsage, "id", BILLING_USAGE_ID);
			ReflectionTestUtils.setField(billingUsage, "createdAt", CREATED_AT);
			return billingUsage;
		});

		// When
		BillingUsageResponse response = billingUsageService.createUsage(request, IDEMPOTENCY_KEY);

		// Then
		ArgumentCaptor<BillingUsage> captor = ArgumentCaptor.forClass(BillingUsage.class);
		verify(billingUsageRepository).save(captor.capture());
		BillingUsage savedUsage = captor.getValue();
		assertThat(savedUsage.getUser()).isSameAs(user);
		assertThat(savedUsage.getProject()).isSameAs(project);
		assertThat(savedUsage.getPromptTokens()).isEqualTo(120L);
		assertThat(savedUsage.getCompletionTokens()).isEqualTo(30L);
		assertThat(savedUsage.getTotalTokens()).isEqualTo(150L);
		assertThat(savedUsage.getModelName()).isEqualTo("gpt-test");
		assertThat(savedUsage.getReportedAt()).isEqualTo(REPORTED_AT);
		assertThat(savedUsage.getIdempotencyKey()).isEqualTo(IDEMPOTENCY_KEY);
		assertThat(savedUsage.getUsagePayloadJson()).contains("\"prompt_tokens\":120");

		assertThat(response.getBillingUsageId()).isEqualTo(BILLING_USAGE_ID);
		assertThat(response.getUserId()).isEqualTo(USER_ID);
		assertThat(response.getProjectId()).isEqualTo(PROJECT_ID);
	}

	@Test
	@DisplayName("같은 Idempotency Key로 보고된 사용량은 중복 저장하지 않고 기존 결과를 반환한다.")
	void createUsageWithDuplicateIdempotencyKey() {
		// Given
		BillingUsage existingUsage = createBillingUsage(IDEMPOTENCY_KEY);
		ReflectionTestUtils.setField(existingUsage, "id", BILLING_USAGE_ID);
		ReflectionTestUtils.setField(existingUsage, "createdAt", CREATED_AT);
		when(billingUsageRepository.findByIdempotencyKey(IDEMPOTENCY_KEY)).thenReturn(Optional.of(existingUsage));

		// When
		BillingUsageResponse response = billingUsageService.createUsage(
			createRequest(120L, 30L, 150L, "gpt-test", REPORTED_AT_TEXT),
			IDEMPOTENCY_KEY
		);

		// Then
		assertThat(response.getBillingUsageId()).isEqualTo(BILLING_USAGE_ID);
		verify(billingUsageRepository, never()).save(any(BillingUsage.class));
		verifyNoInteractions(userRepository, projectRepository);
	}

	@Test
	@DisplayName("modelName이 비어 있으면 unknown으로 저장한다.")
	void createUsageWithBlankModelName() {
		// Given
		BillingUsageCreateRequest request = createRequest(1L, 2L, 3L, "   ", REPORTED_AT_TEXT);
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(billingUsageRepository.save(any(BillingUsage.class))).thenAnswer(invocation -> invocation.getArgument(0));

		// When
		billingUsageService.createUsage(request, null);

		// Then
		ArgumentCaptor<BillingUsage> captor = ArgumentCaptor.forClass(BillingUsage.class);
		verify(billingUsageRepository).save(captor.capture());
		assertThat(captor.getValue().getModelName()).isEqualTo("unknown");
	}

	@Test
	@DisplayName("Idempotency Key가 없으면 요청마다 사용량을 저장한다.")
	void createUsageWithoutIdempotencyKey() {
		// Given
		BillingUsageCreateRequest request = createRequest(1L, 2L, 3L, "gpt-test", REPORTED_AT_TEXT);
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(billingUsageRepository.save(any(BillingUsage.class))).thenAnswer(invocation -> invocation.getArgument(0));

		// When
		billingUsageService.createUsage(request, null);
		billingUsageService.createUsage(request, null);

		// Then
		verify(billingUsageRepository, never()).findByIdempotencyKey(any());
		verify(billingUsageRepository, org.mockito.Mockito.times(2)).save(any(BillingUsage.class));
	}

	@Test
	@DisplayName("token 값이 음수이면 예외가 발생한다.")
	void failWhenTokenIsNegative() {
		// Given
		BillingUsageCreateRequest request = createRequest(-1L, 0L, 0L, "gpt-test", REPORTED_AT_TEXT);
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));

		// When & Then
		assertThatThrownBy(() -> billingUsageService.createUsage(request, null))
			.isInstanceOf(CustomException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.BILLING_USAGE_TOKEN_INVALID);
		verify(billingUsageRepository, never()).save(any(BillingUsage.class));
	}

	@Test
	@DisplayName("존재하지 않는 userId이면 예외가 발생한다.")
	void failWhenUserNotFound() {
		// Given
		BillingUsageCreateRequest request = createRequest(1L, 2L, 3L, "gpt-test", REPORTED_AT_TEXT);
		when(userRepository.findById(USER_ID)).thenReturn(Optional.empty());

		// When & Then
		assertThatThrownBy(() -> billingUsageService.createUsage(request, null))
			.isInstanceOf(CustomException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.USER_NOT_FOUND);
		verifyNoInteractions(projectRepository);
		verify(billingUsageRepository, never()).save(any(BillingUsage.class));
	}

	@Test
	@DisplayName("존재하지 않는 projectId이면 예외가 발생한다.")
	void failWhenProjectNotFound() {
		// Given
		BillingUsageCreateRequest request = createRequest(1L, 2L, 3L, "gpt-test", REPORTED_AT_TEXT);
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.empty());

		// When & Then
		assertThatThrownBy(() -> billingUsageService.createUsage(request, null))
			.isInstanceOf(CustomException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.PROJECT_NOT_FOUND);
		verify(billingUsageRepository, never()).save(any(BillingUsage.class));
	}

	private BillingUsageCreateRequest createRequest(
		Long promptTokens,
		Long completionTokens,
		Long totalTokens,
		String modelName,
		String timestamp
	) {
		BillingUsageMetricsRequest usage = new BillingUsageMetricsRequest();
		ReflectionTestUtils.setField(usage, "promptTokens", promptTokens);
		ReflectionTestUtils.setField(usage, "completionTokens", completionTokens);
		ReflectionTestUtils.setField(usage, "totalTokens", totalTokens);
		ReflectionTestUtils.setField(usage, "modelName", modelName);

		BillingUsageCreateRequest request = new BillingUsageCreateRequest();
		ReflectionTestUtils.setField(request, "userId", USER_ID);
		ReflectionTestUtils.setField(request, "projectId", PROJECT_ID);
		ReflectionTestUtils.setField(request, "usage", usage);
		ReflectionTestUtils.setField(request, "timestamp", timestamp);
		return request;
	}

	private BillingUsage createBillingUsage(String idempotencyKey) {
		return BillingUsage.builder()
			.user(user)
			.project(project)
			.promptTokens(120L)
			.completionTokens(30L)
			.totalTokens(150L)
			.modelName("gpt-test")
			.reportedAt(REPORTED_AT)
			.idempotencyKey(idempotencyKey)
			.usagePayloadJson("{\"prompt_tokens\":120}")
			.build();
	}

	private User createUser() {
		User newUser = User.builder()
			.employeeNumber("B187001")
			.name("Billing User")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(newUser, "id", USER_ID);
		return newUser;
	}

	private Project createProject(User createdByUser) {
		Project newProject = Project.builder()
			.name("Billing Project")
			.createdByUser(createdByUser)
			.projectAdminUser(createdByUser)
			.build();
		ReflectionTestUtils.setField(newProject, "id", PROJECT_ID);
		return newProject;
	}
}
