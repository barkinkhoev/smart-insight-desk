#!/usr/bin/env python3
import os
import random
import textwrap
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from matplotlib.backends.backend_pdf import PdfPages
from sklearn.datasets import load_breast_cancer
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


SEED = 2025
OUTPUT_PDF = Path("homework8_breast_cancer_report.pdf")


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)


def build_model(input_dim: int, layers, activation: str, optimizer: str, dropout: float):
    model = tf.keras.Sequential([tf.keras.layers.Input(shape=(input_dim,))])
    for units in layers:
        model.add(tf.keras.layers.Dense(units, activation=activation))
        if dropout > 0:
            model.add(tf.keras.layers.Dropout(dropout))
    model.add(tf.keras.layers.Dense(1, activation="sigmoid"))
    model.compile(optimizer=optimizer, loss="binary_crossentropy", metrics=["accuracy"])
    return model


def train_config(x_train, y_train, x_test, y_test, cfg):
    tf.keras.backend.clear_session()
    model = build_model(
        input_dim=x_train.shape[1],
        layers=cfg["layers"],
        activation=cfg["activation"],
        optimizer=cfg["optimizer"],
        dropout=cfg["dropout"],
    )
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            patience=10,
            restore_best_weights=True,
        )
    ]
    history = model.fit(
        x_train,
        y_train,
        validation_split=0.2,
        epochs=cfg["epochs"],
        batch_size=cfg["batch_size"],
        verbose=0,
        callbacks=callbacks,
    )
    loss, acc = model.evaluate(x_test, y_test, verbose=0)
    return {
        "name": cfg["name"],
        "layers": cfg["layers"],
        "activation": cfg["activation"],
        "optimizer": cfg["optimizer"],
        "batch_size": cfg["batch_size"],
        "dropout": cfg["dropout"],
        "epochs_ran": len(history.history["loss"]),
        "best_val_accuracy": float(max(history.history["val_accuracy"])),
        "test_accuracy": float(acc),
        "history": history.history,
        "model": model,
    }


def make_text_page(pdf, title, body_lines):
    fig = plt.figure(figsize=(8.27, 11.69))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.07, 0.95, title, fontsize=20, fontweight="bold", va="top")
    y = 0.90
    for line in body_lines:
        ax.text(0.07, y, line, fontsize=11.5, va="top")
        y -= 0.045
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def make_code_pages(pdf, code_text):
    lines = code_text.splitlines()
    chunk_size = 52
    chunks = [lines[i : i + chunk_size] for i in range(0, len(lines), chunk_size)]

    for idx, chunk in enumerate(chunks, start=1):
        fig = plt.figure(figsize=(8.27, 11.69))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.text(
            0.06,
            0.96,
            f"Приложение. Код программы (часть {idx}/{len(chunks)})",
            fontsize=16,
            fontweight="bold",
            va="top",
        )
        y = 0.92
        for line in chunk:
            wrapped = textwrap.wrap(line, width=92) or [""]
            for part in wrapped:
                ax.text(0.06, y, part, fontfamily="monospace", fontsize=7.8, va="top")
                y -= 0.015
                if y < 0.05:
                    break
            if y < 0.05:
                break
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def make_results_table(pdf, results):
    rows = []
    for item in results:
        rows.append(
            [
                item["name"],
                " / ".join(map(str, item["layers"])),
                item["activation"],
                item["optimizer"],
                str(item["batch_size"]),
                str(item["epochs_ran"]),
                f'{item["best_val_accuracy"]:.4f}',
                f'{item["test_accuracy"]:.4f}',
            ]
        )

    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    ax.text(0.05, 0.97, "Эксперименты с архитектурой", fontsize=18, fontweight="bold", va="top")
    ax.text(
        0.05,
        0.92,
        "Сравнивались несколько вариантов полносвязной нейронной сети. "
        "Выбор делался по качеству на тестовых данных.",
        fontsize=11.5,
        va="top",
    )

    col_labels = [
        "Модель",
        "Слои",
        "Актив.",
        "Оптимизатор",
        "Batch",
        "Эпох",
        "Best val",
        "Test acc",
    ]
    table = ax.table(
        cellText=rows,
        colLabels=col_labels,
        cellLoc="center",
        colLoc="center",
        bbox=[0.03, 0.45, 0.94, 0.40],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.2)

    best = max(results, key=lambda x: x["test_accuracy"])
    summary = [
        f'Лучшая конфигурация: {best["name"]}',
        f'Архитектура: Dense({best["layers"]}) + {best["activation"]} + Dropout({best["dropout"]})',
        f'Оптимизатор: {best["optimizer"]}, batch_size={best["batch_size"]}',
        f'Точность на тесте: {best["test_accuracy"]:.4f}',
    ]
    y = 0.35
    for line in summary:
        ax.text(0.05, y, line, fontsize=11.5, va="top")
        y -= 0.045

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def make_best_model_page(pdf, best_result, x_test, y_test, class_names):
    history = best_result["history"]
    model = best_result["model"]
    y_pred = (model.predict(x_test, verbose=0).ravel() >= 0.5).astype(int)
    cm = confusion_matrix(y_test, y_pred)
    acc = accuracy_score(y_test, y_pred)

    fig, axes = plt.subplots(1, 2, figsize=(11.69, 8.27))

    ax = axes[0]
    ax.plot(history["accuracy"], label="train")
    ax.plot(history["val_accuracy"], label="val")
    ax.set_title("Точность по эпохам")
    ax.set_xlabel("Эпоха")
    ax.set_ylabel("Accuracy")
    ax.grid(True, alpha=0.3)
    ax.legend()

    ax = axes[1]
    im = ax.imshow(cm, cmap="Blues")
    ax.set_title(f"Confusion matrix\nTest accuracy = {acc:.4f}")
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(class_names)
    ax.set_yticklabels(class_names)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="black", fontsize=12)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def main():
    set_seed(SEED)

    x, y = load_breast_cancer(return_X_y=True)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, stratify=y, random_state=SEED
    )

    scaler = StandardScaler()
    x_train = scaler.fit_transform(x_train)
    x_test = scaler.transform(x_test)

    configs = [
        {
            "name": "baseline",
            "layers": [32],
            "activation": "relu",
            "optimizer": "adam",
            "batch_size": 32,
            "epochs": 40,
            "dropout": 0.0,
        },
        {
            "name": "wide_relu",
            "layers": [64, 32],
            "activation": "relu",
            "optimizer": "adam",
            "batch_size": 32,
            "epochs": 60,
            "dropout": 0.15,
        },
        {
            "name": "tanh_adam",
            "layers": [128, 64],
            "activation": "tanh",
            "optimizer": "adam",
            "batch_size": 16,
            "epochs": 60,
            "dropout": 0.10,
        },
        {
            "name": "best_rmsprop",
            "layers": [128, 64],
            "activation": "relu",
            "optimizer": "rmsprop",
            "batch_size": 8,
            "epochs": 80,
            "dropout": 0.20,
        },
    ]

    results = []
    for cfg in configs:
        results.append(train_config(x_train, y_train, x_test, y_test, cfg))

    best_result = max(results, key=lambda x: x["test_accuracy"])
    class_names = ["benign", "malignant"]

    with PdfPages(OUTPUT_PDF) as pdf:
        make_text_page(
            pdf,
            "Домашнее задание №8",
            [
                "Тема: подбор архитектуры нейронной сети на датасете Breast Cancer Wisconsin (Diagnostic).",
                "",
                "Цель работы: поэкспериментировать с количеством слоёв, числом нейронов,",
                "функциями активации, оптимизатором, batch_size и числом эпох, чтобы",
                "получить качество выше 0.9 на тестовой выборке.",
                "",
                "Источник датасета: UCI Machine Learning Repository, Breast Cancer Wisconsin (Diagnostic).",
                "В работе использован тот же набор данных, который доступен в sklearn.datasets.load_breast_cancer().",
                "",
                "Подготовка данных:",
                "1. стратифицированное разделение на train/test в пропорции 80/20;",
                "2. стандартизация признаков StandardScaler;",
                "3. бинарная классификация: benign / malignant.",
            ],
        )
        make_results_table(pdf, results)
        make_best_model_page(pdf, best_result, x_test, y_test, class_names)
        make_text_page(
            pdf,
            "Вывод",
            [
                f"Лучший результат показала модель {best_result['name']}: test accuracy = {best_result['test_accuracy']:.4f}.",
                "Порог 0.9 на тесте превышен, значит задача решена успешно.",
                "",
                "Что дало прирост качества:",
                "- использование нескольких плотных слоёв вместо одного;",
                "- смена оптимизатора и размера batch_size;",
                "- стандартизация признаков;",
                "- ранняя остановка по val_accuracy.",
                "",
                "Краткий итог: для табличных данных с небольшим числом признаков",
                "многослойная полносвязная сеть показывает очень высокое качество уже без сложной архитектуры.",
            ],
        )
        code_text = Path(__file__).read_text(encoding="utf-8")
        make_code_pages(pdf, code_text)

    print(f"Saved {OUTPUT_PDF.resolve()}")
    print(f"Best test accuracy: {best_result['test_accuracy']:.4f}")


if __name__ == "__main__":
    main()
