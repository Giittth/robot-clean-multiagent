"""
    模型评估
    上下文相关性  忠诚度  答案相关性
"""

import asyncio
import os
import json
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.evaluation import FaithfulnessEvaluator, RelevancyEvaluator, BatchEvalRunner
from llama_index.core.postprocessor import MetadataReplacementPostProcessor
from llama_index.core.node_parser import SentenceWindowNodeParser, SentenceSplitter
from llama_index.core.schema import Document
from llama_index.core.llama_dataset.generator import RagDatasetGenerator
from llama_index.core.llama_dataset import LabelledRagDataset
from langchain_ollama import OllamaLLM
from llama_index.llms.langchain import LangChainLLM

from backend.rag.vector.vector_store_retriever import vector_store
from backend.config import settings
from backend.utils.file_handler import get_abs_path
from backend.rag.rag_service import rag_services


os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 全局使用稳定向量
Settings.embed_model = FastEmbedEmbedding(
    model_name="BAAI/bge-small-zh-v1.5",
    cache_dir="./models"     # 指定本地缓存目录
)

async def evaluate_query_engine():
    """创建llamaindex评估引擎"""

    # 创建 Ollama LLM
    langchain_ollama = OllamaLLM(
        model=rag_services.model.model,
        base_url=rag_services.model.base_url,
        temperature=rag_services.model.temperature
    )
    Settings.llm = LangChainLLM(llm=langchain_ollama)
    print(1)

    # 加载向量库中的数据
    docs = vector_store.get_data()
    # 将数据转换为Document对象
    documents = []
    for idx in range(len(docs['documents'])):
        text = docs['documents'][idx]
        metadata = docs['metadatas'][idx] if idx < len(docs['metadatas']) else {}

        if text and len(str(text).strip()) > 10:
            doc = Document(
                text=str(text),
                metadata=metadata
            )
            documents.append(doc)

    if not documents:
        raise ValueError("向量库中没有有效的文档数据")
    print(2)

    # 生成问答对
    if os.path.exists(get_abs_path(settings.evaluate_ques2query_path)):
        response_eval_dataset = LabelledRagDataset.from_json(get_abs_path(settings.evaluate_ques2query_path))
    else:
        dataset_generator = RagDatasetGenerator.from_documents(documents[:5], llm=Settings.llm, num_questions_per_chunk=2)
        response_eval_dataset = await dataset_generator.agenerate_dataset_from_nodes()
        response_eval_dataset.save_json(get_abs_path(settings.evaluate_ques2query_path))

    print(3)
    # 创建 上下文窗口索引引擎
    # 创建索引切割器
    sentence_window_parser = SentenceWindowNodeParser.from_defaults(
        window_size=3,          # 句子前后各看 三句
        window_metadata_key="window",       # 把 “完整窗口文本” 存在 metadata 里，key 名叫 window
        original_text_metadata_key="original_text"      # 把 “真正命中的那 1 句话” 存在 metadata 里
    )
    print(3.1)
    # 进行切割并向量库
    sentence_nodes = sentence_window_parser.get_nodes_from_documents(documents[:5])
    print(3.2)
    sentence_index = VectorStoreIndex(
        sentence_nodes,
        show_progress=True
    )
    print(3.3)
    # 加载已有向量库
    # sentence_index = VectorStoreIndex.from_vector_store(vector_store)
    sentence_retriever = sentence_index.as_retriever(similarity_top_k=2)
    # 创建 句子窗口检索引擎
    sentence_query_engine = sentence_index.as_query_engine(
        similarity_top_k=2,
        node_postprocessors=[
            MetadataReplacementPostProcessor(target_metadata_key="window")
        ],
    )
    print(4)
    # 创建 基础索引引擎
    # 创建索引切割器
    base_parser = SentenceSplitter(chunk_size=512)
    # 进行切割并向量库
    base_nodes = base_parser.get_nodes_from_documents(documents[:5])
    base_index = VectorStoreIndex(
        base_nodes,
        show_progress=True
    )
    base_retriever = base_index.as_retriever(similarity_top_k=2)
    # 创建基础检索引擎
    base_query_engine = base_index.as_query_engine(similarity_top_k=2)


    # =======================================RAGAS=================================================
    #
    # # 3. 准备两种索引的数据
    # base_data = {"question": [], "contexts": [], "answer": [], "ground_truth": []}
    # sentence_data = {"question": [], "contexts": [], "answer": [], "ground_truth": []}
    #
    #
    # for example in response_eval_dataset.examples:
    #     query = example.query
    #     ground_truth = example.reference_answer
    #
    #     # 普通索引查询
    #     base_response = await base_query_engine.aquery(query)
    #     base_data["question"].append(query)
    #     base_data["contexts"].append([node.text for node in base_response.source_nodes])
    #     base_data["answer"].append(str(base_response))
    #     base_data["ground_truth"].append(ground_truth)
    #
    #     # 句子窗口索引查询
    #     sentence_response = await sentence_query_engine.aquery(query)
    #     sentence_data["question"].append(query)
    #     sentence_data["contexts"].append([node.text for node in sentence_response.source_nodes])
    #     sentence_data["answer"].append(str(sentence_response))
    #     sentence_data["ground_truth"].append(ground_truth)
    #
    # # 4. 转换为 HuggingFace Dataset
    # base_dataset = Dataset.from_dict(base_data)
    # sentence_dataset = Dataset.from_dict(sentence_data)
    #
    # # 5. 分别评估
    # print("\n评估普通索引...")
    # base_result = evaluate(
    #     dataset=base_dataset,
    #     metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    #     llm=Settings.llm,
    #     embeddings=Settings.embed_model,
    # )
    #
    # print("\n评估句子窗口索引...")
    # sentence_result = evaluate(
    #     dataset=sentence_dataset,
    #     metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    #     llm=Settings.llm,
    #     embeddings=Settings.embed_model,
    # )
    #
    # # 7. 提取评估分数
    # # 转换为DataFrame后取平均值
    # base_df = base_result.to_pandas()
    # sentence_df = sentence_result.to_pandas()
    #
    # # 提取每个指标的平均值
    # base_scores = {
    #     "faithfulness": base_df["faithfulness"].mean(),
    #     "answer_relevancy": base_df["answer_relevancy"].mean(),
    #     "context_precision": base_df["context_precision"].mean(),
    #     "context_recall": base_df["context_recall"].mean(),
    # }
    # sentence_scores = {
    #     "faithfulness": sentence_df["faithfulness"].mean(),
    #     "answer_relevancy": sentence_df["answer_relevancy"].mean(),
    #     "context_precision": sentence_df["context_precision"].mean(),
    #     "context_recall": sentence_df["context_recall"].mean(),
    # }
    #
    # # 计算对比结果
    # comparison = {}
    # for metric in base_scores.keys():
    #     diff = sentence_scores[metric] - base_scores[metric]
    #     improvement_pct = (diff / base_scores[metric] * 100) if base_scores[metric] > 0 else 0
    #     comparison[metric] = {
    #         "base_index": base_scores[metric],
    #         "sentence_window_index": sentence_scores[metric],
    #         "difference": diff,
    #         "improvement_percentage": round(improvement_pct, 2),
    #         "better_index": "sentence_window" if diff > 0 else "base"
    #     }
    #
    # # 打印结果
    # print("\n" + "=" * 50)
    # print("评估结果")
    # print("=" * 50)
    #
    # print("\n普通索引:")
    # print(f"  Faithfulness: {base_df['faithfulness'].mean():.2%}")
    # print(f"  Answer Relevancy: {base_df['answer_relevancy'].mean():.2%}")
    # print(f"  Context Precision: {base_df['context_precision'].mean():.2%}")
    # print(f"  Context Recall: {base_df['context_recall'].mean():.2%}")
    #
    # print("\n句子窗口索引:")
    # print(f"  Faithfulness: {sentence_df['faithfulness'].mean():.2%}")
    # print(f"  Answer Relevancy: {sentence_df['answer_relevancy'].mean():.2%}")
    # print(f"  Context Precision: {sentence_df['context_precision'].mean():.2%}")
    # print(f"  Context Recall: {sentence_df['context_recall'].mean():.2%}")
    #
    # # 对比
    # print("\n对比（句子窗口 - 普通）:")
    # print(f"  Faithfulness: {(sentence_df['faithfulness'].mean() - base_df['faithfulness'].mean()):+.2%}")
    # print(f"  Answer Relevancy: {(sentence_df['answer_relevancy'].mean() - base_df['answer_relevancy'].mean()):+.2%}")
    #
    # # 保存 JSON 格式
    # # 构建最终 JSON
    # final_results = {
    #     "evaluation_info": {
    #         "timestamp": datetime.now().isoformat(),
    #         "total_queries": len(base_df),
    #     },
    #     "summary": {
    #         "base_index": base_scores,
    #         "sentence_window_index": sentence_scores,
    #         "comparison": comparison,
    #         "overall_better_index": "sentence_window" if sentence_scores["faithfulness"] > base_scores[
    #             "faithfulness"] else "base",
    #     }
    # }
    #
    # # 保存 JSON 文件
    # json_path = get_abs_path("evaluate/ragas_evaluation_results.json")
    # os.makedirs(os.path.dirname(json_path), exist_ok=True)
    #
    # with open(json_path, "w", encoding="utf-8") as f:
    #     json.dump(final_results, f, ensure_ascii=False, indent=2)
    #
    # print(f"结果已保存到: {json_path}")
    # print(json.dumps(final_results, ensure_ascii=False, indent=2))


# ==============================LlamaIndex======================================================

    # 定义评估指标
    faithfulness_evaluator = FaithfulnessEvaluator(Settings.llm)
    relevancy_evaluator = RelevancyEvaluator(Settings.llm)
    evaluator = {"faithfulness": faithfulness_evaluator, "relevancy": relevancy_evaluator}
    print(5)
    # 获取数据集
    queries = [text.query for text in response_eval_dataset.examples]

    # 评估“句子窗口检索”引擎
    sentence_runner = BatchEvalRunner(evaluator, workers=2, show_progress=True)     # 同时开2个线程并行跑任务
    print(5.1)
    print(5.11)
    print(5.12)
    print(5.13)
    try:
        sentence_runner_results = await sentence_runner.aevaluate_queries(queries=queries[:5], query_engine=sentence_query_engine)
        print(5.2)
    except Exception as e:
        print(f"评估失败: {e}")
        sentence_runner_results = {"faithfulness": [], "relevancy": []}

    # 评估“常规分块检索”引擎
    base_runner = BatchEvalRunner(evaluator, workers=2, show_progress=True)
    print(5.3)
    base_runner_results = await base_runner.aevaluate_queries(queries=queries[:5], query_engine=base_query_engine)
    print(6)

    def calc_response_score(results, metric):
        if results and results.get(metric):
            scores = results[metric]
            return sum(score.passing for score in scores) / len(scores)
        return 0

    # 句子窗口索引 评估结果
    sentence_faith = calc_response_score(sentence_runner_results, "faithfulness")
    sentence_relevancy = calc_response_score(sentence_runner_results, "relevancy")

    # 基础索引 评估结果
    base_faith = calc_response_score(base_runner_results, "faithfulness")
    base_relevancy = calc_response_score(base_runner_results, "relevancy")
    print(7)
    # 打印结果
    print("\n句子窗口索引:")
    print(f" Faithfulness: {sentence_faith:.2%}")
    print(f" Relevancy: {sentence_relevancy:.2%}")

    print("\n基础索引:")
    print(f" Faithfulness: {base_faith:.2%}")
    print(f" Relevancy: {base_relevancy:.2%}")

    # 保存结果
    llamaindex_evaluate = {
        "sentence_faith": sentence_faith,
        "sentence_relevancy": sentence_relevancy,
        "base_faith": base_faith,
        "base_relevancy": base_relevancy,
    }

    filepath = get_abs_path("evaluate/llamaindex_evaluate.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = []

    # 记录评估的次数
    llamaindex_evaluate["count"] = len(history) + 1
    history.append(llamaindex_evaluate)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)



if __name__ == "__main__":
    # print(vector_store.get_data())
    # print(type(vector_store.get_data()))
    asyncio.run(evaluate_query_engine())

