plugins {
    java
    id("org.springframework.boot") version "4.0.6"
}

group = "com.personallab"
version = "0.1.0"

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-jackson:4.0.6")
    implementation("org.springframework.boot:spring-boot-starter-webmvc:4.0.6")
    testImplementation("org.springframework.boot:spring-boot-starter-webmvc-test:4.0.6")
    testImplementation("org.springframework.boot:spring-boot-starter-test:4.0.6")
    testImplementation("com.tngtech.archunit:archunit-junit5:1.4.1")
}

tasks.withType<Test> {
    useJUnitPlatform()
}
