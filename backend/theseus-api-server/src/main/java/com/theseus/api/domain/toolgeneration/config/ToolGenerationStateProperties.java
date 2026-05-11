package com.theseus.api.domain.toolgeneration.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "theseus.tool-generation")
public class ToolGenerationStateProperties {

	private long stateTtlMinutes = 30;
	private long sseTimeoutMillis = 1800000;
	private long runTimeoutMinutes = 30;
	private long runTimeoutCheckDelayMillis = 60000;

	public ToolGenerationStateProperties() {
	}

	public ToolGenerationStateProperties(long stateTtlMinutes, long sseTimeoutMillis) {
		this.stateTtlMinutes = stateTtlMinutes;
		this.sseTimeoutMillis = sseTimeoutMillis;
	}

	public Duration stateTtl() {
		return Duration.ofMinutes(stateTtlMinutes);
	}

	public long sseTimeoutMillis() {
		return sseTimeoutMillis;
	}

	public Duration runTimeout() {
		return Duration.ofMinutes(runTimeoutMinutes);
	}

	public long getStateTtlMinutes() {
		return stateTtlMinutes;
	}

	public void setStateTtlMinutes(long stateTtlMinutes) {
		this.stateTtlMinutes = stateTtlMinutes;
	}

	public long getSseTimeoutMillis() {
		return sseTimeoutMillis;
	}

	public void setSseTimeoutMillis(long sseTimeoutMillis) {
		this.sseTimeoutMillis = sseTimeoutMillis;
	}

	public long getRunTimeoutMinutes() {
		return runTimeoutMinutes;
	}

	public void setRunTimeoutMinutes(long runTimeoutMinutes) {
		this.runTimeoutMinutes = runTimeoutMinutes;
	}

	public long getRunTimeoutCheckDelayMillis() {
		return runTimeoutCheckDelayMillis;
	}

	public void setRunTimeoutCheckDelayMillis(long runTimeoutCheckDelayMillis) {
		this.runTimeoutCheckDelayMillis = runTimeoutCheckDelayMillis;
	}
}
